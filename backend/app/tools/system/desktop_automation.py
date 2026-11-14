import io
import os
import sys
import time
import base64
import ctypes
import webbrowser
import subprocess
from typing import Dict, Any, Optional, Tuple
from ctypes import wintypes
from PIL import Image
from backend.app.tools.base import BaseTool, ToolParameter
from backend.app.tools.registry import tool_registry
from backend.app.core.logging import logger

# Windows Native API Constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x000C
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_MAPPING = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "escape": 0x1B,
    "esc": 0x1B,
    "win": 0x5B,
    "windows": 0x5B,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B
}

_last_frame_info: Dict[str, int] = {}
_ocr_engine = None


def _attach_thread_to_input_desktop() -> bool:
    """Ensures current thread is attached to the interactive input desktop (winsta0/default)."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        user32.OpenInputDesktop.restype = wintypes.HANDLE
        user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        user32.SetThreadDesktop.restype = wintypes.BOOL
        user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
        # 0x1FF = DESKTOP_ALL
        h_input = user32.OpenInputDesktop(0, False, 0x1FF)
        if h_input:
            return bool(user32.SetThreadDesktop(h_input))
    except Exception as e:
        logger.debug(f"Failed to attach thread desktop: {e}")
    return False


def _get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
        except Exception as e:
            logger.warning(f"Failed to initialize RapidOCR: {e}")
            return None
    return _ocr_engine


def _ensure_dpi_awareness():
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def _get_screen_size() -> Tuple[int, int]:
    _ensure_dpi_awareness()
    if sys.platform == "win32":
        try:
            u32 = ctypes.windll.user32
            w = u32.GetSystemMetrics(0)
            h = u32.GetSystemMetrics(1)
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    return 1920, 1080


def _capture_screen_bitblt() -> Optional[Image.Image]:
    """Capture full desktop using native Windows GDI BitBlt for maximum speed & reliability."""
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        w, h = _get_screen_size()

        hwin = user32.GetDesktopWindow()
        hwindc = user32.GetWindowDC(hwin)
        if not hwindc:
            return None

        srcdc = gdi32.CreateCompatibleDC(hwindc)
        bmp = gdi32.CreateCompatibleBitmap(hwindc, w, h)
        gdi32.SelectObject(srcdc, bmp)

        # SRCCOPY = 0x00CC0020, CAPTUREBLT = 0x40000000
        gdi32.BitBlt(srcdc, 0, 0, w, h, hwindc, 0, 0, 0x00CC0020 | 0x40000000)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # top-down DIB
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf = ctypes.create_string_buffer(w * h * 4)
        got = gdi32.GetDIBits(srcdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)

        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(srcdc)
        user32.ReleaseDC(hwin, hwindc)

        if got == h:
            return Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1).convert('RGB')
    except Exception as e:
        logger.warning(f"Native BitBlt screen capture failed: {e}")
    return None


def _capture_raw_screen_image() -> Optional[Image.Image]:
    """Captures desktop screen using multi-tier fallback with interactive desktop attachment."""
    _ensure_dpi_awareness()
    _attach_thread_to_input_desktop()
    im = None

    # 1. Pillow ImageGrab with interactive desktop
    try:
        from PIL import ImageGrab
        im = ImageGrab.grab()
        c = im.getcolors(maxcolors=2)
        if c is not None and len(c) == 1:
            im = None
    except Exception:
        im = None

    if im is None:
        try:
            from PIL import ImageGrab
            im = ImageGrab.grab(all_screens=True)
            c = im.getcolors(maxcolors=2)
            if c is not None and len(c) == 1:
                im = None
        except Exception:
            im = None

    # 2. Native BitBlt
    if im is None:
        im = _capture_screen_bitblt()
        if im is not None:
            c = im.getcolors(maxcolors=2)
            if c is not None and len(c) == 1:
                im = None

    # 3. PowerShell Drawing fallback
    if im is None and sys.platform == "win32":
        try:
            tmp_png = os.path.join(os.environ.get("TEMP", "."), f"nova_scr_{os.getpid()}_{int(time.time()*1000)}.png")
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "Add-Type -AssemblyName System.Drawing; "
                "$s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                "$b = New-Object System.Drawing.Bitmap $s.Width, $s.Height; "
                "$g = [System.Drawing.Graphics]::FromImage($b); "
                "$g.CopyFromScreen($s.Location, [System.Drawing.Point]::Empty, $s.Size); "
                f"$b.Save('{tmp_png}', [System.Drawing.Imaging.ImageFormat]::Png); "
                "$g.Dispose(); $b.Dispose();"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            if os.path.isfile(tmp_png):
                im = Image.open(tmp_png).convert('RGB')
                os.remove(tmp_png)
        except Exception:
            pass

    return im


def _take_screenshot() -> Dict[str, Any]:
    global _last_frame_info
    w, h = _get_screen_size()
    im = _capture_raw_screen_image()

    if im is None:
        return {
            "status": "warning",
            "action": "screenshot",
            "screen_width": w,
            "screen_height": h,
            "image_base64": None,
            "message": f"Could not capture desktop screen ({w}x{h}). Please ensure an interactive desktop session is active."
        }

    # Store frame info and scale if needed (only downscale if screen is > 1920)
    frame_w = im.width
    frame_h = im.height
    if frame_w > 1920:
        scale = 1920.0 / frame_w
        frame_w = 1920
        frame_h = int(im.height * scale)
        im = im.resize((frame_w, frame_h), Image.Resampling.LANCZOS)

    _last_frame_info = {
        "screen_w": w,
        "screen_h": h,
        "frame_w": frame_w,
        "frame_h": frame_h
    }

    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "status": "success",
        "action": "screenshot",
        "screen_width": w,
        "screen_height": h,
        "frame_width": frame_w,
        "frame_height": frame_h,
        "image_base64": b64,
        "mime_type": "image/png",
        "message": f"Captured desktop screen. Screen: {w}x{h}, Visual frame: {frame_w}x{frame_h}. Coordinates you specify will be automatically mapped to physical screen pixels."
    }


def _ocr_screen(query: Optional[str] = None, auto_click: bool = False, double_click: bool = False) -> Dict[str, Any]:
    """Runs RapidOCR on current screen to find UI buttons, text elements, and exact coordinates."""
    im = _capture_raw_screen_image()
    if im is None:
        return {"status": "error", "message": "Failed to capture desktop screen for OCR."}

    w, h = im.size
    ocr = _get_ocr_engine()
    if ocr is None:
        return {"status": "error", "message": "RapidOCR engine is not available."}

    try:
        import numpy as np
        img_np = np.array(im)
        res, _ = ocr(img_np)
    except Exception as e:
        return {"status": "error", "message": f"OCR processing failed: {e}"}

    items = []
    if res:
        for box, text_val, score in res:
            cx = int((box[0][0] + box[2][0]) / 2)
            cy = int((box[0][1] + box[2][1]) / 2)
            bw = int(abs(box[1][0] - box[0][0]))
            bh = int(abs(box[2][1] - box[1][1]))
            items.append({
                "text": str(text_val).strip(),
                "x": cx,
                "y": cy,
                "width": bw,
                "height": bh,
                "score": round(float(score), 3),
                "box": [[int(pt[0]), int(pt[1])] for pt in box]
            })

    if query:
        q_clean = query.strip().lower()
        exact_matches = []
        partial_matches = []
        for it in items:
            t_clean = it["text"].lower()
            if t_clean == q_clean:
                exact_matches.append(it)
            elif q_clean in t_clean or any(word in t_clean for word in q_clean.split()):
                partial_matches.append(it)

        exact_matches.sort(key=lambda x: x["score"], reverse=True)
        partial_matches.sort(key=lambda x: x["score"], reverse=True)
        all_matches = exact_matches + partial_matches

        if not all_matches:
            return {
                "status": "warning",
                "action": "find_text",
                "query": query,
                "found": False,
                "screen_width": w,
                "screen_height": h,
                "message": f"Text '{query}' was not found on screen. {len(items)} other text elements were detected."
            }

        best = all_matches[0]
        result = {
            "status": "success",
            "action": "find_text",
            "query": query,
            "found": True,
            "best_match": best,
            "all_matches": all_matches[:5],
            "total_matches": len(all_matches),
            "screen_width": w,
            "screen_height": h
        }

        if auto_click:
            _mouse_click(best["x"], best["y"], button="left", double=double_click)
            result["clicked"] = True
            result["click_type"] = "double_click" if double_click else "click"
            result["message"] = f"Found '{best['text']}' at ({best['x']}, {best['y']}) and clicked it."
        else:
            result["message"] = f"Found '{best['text']}' at ({best['x']}, {best['y']}). Use click at this coordinate or pass click=True."

        return result

    # No query: return detected text items sorted top-to-bottom, left-to-right
    items.sort(key=lambda it: (it["y"] // 25, it["x"]))
    return {
        "status": "success",
        "action": "ocr",
        "screen_width": w,
        "screen_height": h,
        "total_elements": len(items),
        "elements": items[:80],
        "message": f"OCR detected {len(items)} text elements on screen."
    }


def _map_coords(x: Optional[Any], y: Optional[Any]) -> Tuple[Optional[int], Optional[int]]:
    """Smart coordinate mapping supporting normalized, visual frame, and screen pixels."""
    if x is None or y is None:
        return None, None

    screen_w, screen_h = _get_screen_size()
    frame_w = _last_frame_info.get("frame_w", screen_w)
    frame_h = _last_frame_info.get("frame_h", screen_h)

    try:
        xf = float(x)
        yf = float(y)
    except (ValueError, TypeError):
        return None, None

    # Normalized coordinates (0.0 to 1.0)
    if 0.0 <= xf <= 1.0 and 0.0 <= yf <= 1.0:
        rx = int(round(xf * screen_w))
        ry = int(round(yf * screen_h))
        return max(0, min(screen_w - 1, rx)), max(0, min(screen_h - 1, ry))

    # Visual frame space (scaled down from screen)
    if frame_w != screen_w and (xf <= frame_w and yf <= frame_h):
        scale_x = screen_w / float(frame_w)
        scale_y = screen_h / float(frame_h)
        rx = int(round(xf * scale_x))
        ry = int(round(yf * scale_y))
        return max(0, min(screen_w - 1, rx)), max(0, min(screen_h - 1, ry))

    # Direct physical screen coordinates
    rx = int(round(xf))
    ry = int(round(yf))
    return max(0, min(screen_w - 1, rx)), max(0, min(screen_h - 1, ry))


def _mouse_move(x: int, y: int):
    if sys.platform == "win32":
        mx, my = _map_coords(x, y)
        if mx is not None and my is not None:
            ctypes.windll.user32.SetCursorPos(mx, my)


def _mouse_click(x: Optional[Any] = None, y: Optional[Any] = None, button: str = "left", double: bool = False):
    if sys.platform == "win32":
        u32 = ctypes.windll.user32
        if x is not None and y is not None:
            mx, my = _map_coords(x, y)
            if mx is not None and my is not None:
                u32.SetCursorPos(mx, my)
        time.sleep(0.04)

        b_lower = (button or "left").lower()
        if b_lower == "right":
            down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
        elif b_lower == "middle":
            down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
        else:
            down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

        u32.mouse_event(down_flag, 0, 0, 0, 0)
        u32.mouse_event(up_flag, 0, 0, 0, 0)
        if double:
            time.sleep(0.08)
            u32.mouse_event(down_flag, 0, 0, 0, 0)
            u32.mouse_event(up_flag, 0, 0, 0, 0)


def _mouse_drag(start_x: int, start_y: int, end_x: int, end_y: int):
    if sys.platform == "win32":
        u32 = ctypes.windll.user32
        sx, sy = _map_coords(start_x, start_y)
        ex, ey = _map_coords(end_x, end_y)
        if sx is None or sy is None:
            return
        ex = ex if ex is not None else sx
        ey = ey if ey is not None else sy

        u32.SetCursorPos(sx, sy)
        time.sleep(0.04)
        u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.04)
        steps = 10
        for i in range(1, steps + 1):
            curr_x = int(sx + (ex - sx) * (i / steps))
            curr_y = int(sy + (ey - sy) * (i / steps))
            u32.SetCursorPos(curr_x, curr_y)
            time.sleep(0.015)
        u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _mouse_scroll(clicks: int):
    if sys.platform == "win32":
        u32 = ctypes.windll.user32
        u32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(clicks * 120), 0)


def _keyboard_type(text: str):
    if sys.platform == "win32":
        u32 = ctypes.windll.user32
        for ch in text:
            code = ord(ch)
            u32.keybd_event(0, code, KEYEVENTF_UNICODE, 0)
            u32.keybd_event(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)
            time.sleep(0.008)


def _keyboard_press(key_combo: str):
    if sys.platform == "win32":
        u32 = ctypes.windll.user32
        combo = key_combo.lower().strip()
        parts = [p.strip() for p in combo.split("+")]

        vks = []
        for p in parts:
            if p in VK_MAPPING:
                vks.append(VK_MAPPING[p])
            elif len(p) == 1:
                vks.append(ord(p.upper()))

        for vk in vks:
            u32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.06)
        for vk in reversed(vks):
            u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


tool_desktop_control = BaseTool(
    name="desktop_control",
    description="Controls the desktop GUI environment using mouse, keyboard, and screen OCR element detection. Designed for vision-capable models to operate Windows applications, web browsers, Photoshop, etc. Supports finding UI elements by text label ('find_text') and executing actions in a single rapid turn.",
    category="system",
    risk_level="HIGH",
    requires_approval=False,
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="The desktop action to perform: 'find_text' (locates text/buttons with OCR and optionally clicks), 'ocr' (scans screen and lists all UI text elements with coordinates), 'screenshot', 'click', 'double_click', 'right_click', 'move', 'drag', 'type', 'press_key', 'scroll', 'open_url', 'open_app', 'wait'.",
            enum=["find_text", "ocr", "screenshot", "click", "double_click", "right_click", "move", "drag", "type", "press_key", "scroll", "open_url", "open_app", "wait"]
        ),
        ToolParameter(name="x", type="integer", description="X coordinate on screen (0 to screen width) or on visual frame. If provided to 'type', clicks at (x, y) first to focus before typing.", required=False),
        ToolParameter(name="y", type="integer", description="Y coordinate on screen (0 to screen height) or on visual frame. If provided to 'type', clicks at (x, y) first to focus before typing.", required=False),
        ToolParameter(name="end_x", type="integer", description="Target X coordinate for drag operations", required=False),
        ToolParameter(name="end_y", type="integer", description="Target Y coordinate for drag operations", required=False),
        ToolParameter(name="text", type="string", description="Text to type using keyboard, or text to search for in 'find_text', or URL for 'open_url', or app name for 'open_app'", required=False),
        ToolParameter(name="key", type="string", description="Key or key combination to press (e.g. 'enter', 'tab', 'win', 'win+r', 'alt+d', 'ctrl+l', 'ctrl+t', 'ctrl+c', 'ctrl+v', 'alt+f4')", required=False),
        ToolParameter(name="click", type="boolean", description="Whether to automatically click the found text element when action='find_text'", required=False),
        ToolParameter(name="double_click", type="boolean", description="Whether to double click instead of single click when action='find_text'", required=False),
        ToolParameter(name="press_enter", type="boolean", description="Whether to press Enter after typing text", required=False),
        ToolParameter(name="clear_first", type="boolean", description="Whether to clear existing text (Ctrl+A, Backspace) before typing", required=False),
        ToolParameter(name="scroll_clicks", type="integer", description="Scroll amount: positive to scroll up, negative to scroll down", required=False),
        ToolParameter(name="wait_seconds", type="number", description="Seconds to pause/wait (e.g. 1.0)", required=False)
    ]
)


async def handle_desktop_control(arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    action = (arguments.get("action") or "").lower().strip()
    x = arguments.get("x")
    y = arguments.get("y")
    end_x = arguments.get("end_x")
    end_y = arguments.get("end_y")
    text = arguments.get("text")
    key = arguments.get("key")
    click_flag = bool(arguments.get("click", False))
    double_click_flag = bool(arguments.get("double_click", False))
    press_enter = bool(arguments.get("press_enter", False))
    clear_first = bool(arguments.get("clear_first", False))
    scroll_clicks = arguments.get("scroll_clicks")
    wait_sec = arguments.get("wait_seconds", 0.5)

    try:
        if action == "find_text":
            return _ocr_screen(query=text, auto_click=click_flag, double_click=double_click_flag)

        elif action == "ocr":
            return _ocr_screen(query=None, auto_click=False)

        elif action == "screenshot":
            return _take_screenshot()

        elif action == "click":
            _mouse_click(x, y, button="left", double=False)
            mx, my = _map_coords(x, y)
            return {"status": "success", "action": "click", "screen_x": mx, "screen_y": my, "message": f"Left clicked at ({mx}, {my})"}

        elif action == "double_click":
            _mouse_click(x, y, button="left", double=True)
            mx, my = _map_coords(x, y)
            return {"status": "success", "action": "double_click", "screen_x": mx, "screen_y": my, "message": f"Double clicked at ({mx}, {my})"}

        elif action == "right_click":
            _mouse_click(x, y, button="right", double=False)
            mx, my = _map_coords(x, y)
            return {"status": "success", "action": "right_click", "screen_x": mx, "screen_y": my, "message": f"Right clicked at ({mx}, {my})"}

        elif action == "move":
            if x is not None and y is not None:
                _mouse_move(x, y)
                mx, my = _map_coords(x, y)
                return {"status": "success", "action": "move", "screen_x": mx, "screen_y": my, "message": f"Moved mouse to ({mx}, {my})"}
            return {"status": "error", "message": "Missing x or y coordinate for move"}

        elif action == "drag":
            start_x = x or 0
            start_y = y or 0
            to_x = end_x if end_x is not None else start_x
            to_y = end_y if end_y is not None else start_y
            _mouse_drag(start_x, start_y, to_x, to_y)
            return {"status": "success", "action": "drag", "from": [start_x, start_y], "to": [to_x, to_y]}

        elif action == "scroll":
            clicks = scroll_clicks if scroll_clicks is not None else 3
            _mouse_scroll(clicks)
            return {"status": "success", "action": "scroll", "clicks": clicks}

        elif action == "type":
            if not text:
                return {"status": "error", "message": "Missing text parameter to type"}

            # Auto-focus if coordinates are provided
            if x is not None and y is not None:
                _mouse_click(x, y, button="left", double=False)
                time.sleep(0.12)

            if clear_first:
                _keyboard_press("ctrl+a")
                time.sleep(0.04)
                _keyboard_press("backspace")
                time.sleep(0.04)

            _keyboard_type(text)

            if press_enter:
                time.sleep(0.08)
                _keyboard_press("enter")

            return {
                "status": "success",
                "action": "type",
                "text": text,
                "clicked_at": [x, y] if (x is not None and y is not None) else None,
                "pressed_enter": press_enter
            }

        elif action == "press_key":
            if key:
                _keyboard_press(key)
                return {"status": "success", "action": "press_key", "key": key}
            return {"status": "error", "message": "Missing key parameter"}

        elif action == "open_url":
            target_url = text or (arguments.get("url") if "url" in arguments else None)
            if not target_url:
                return {"status": "error", "message": "Missing url or text parameter for open_url"}
            if not (target_url.startswith("http://") or target_url.startswith("https://")):
                target_url = "https://" + target_url
            webbrowser.open(target_url)
            time.sleep(1.2)
            return {
                "status": "success",
                "action": "open_url",
                "url": target_url,
                "message": f"Opened '{target_url}' in browser. Call action='screenshot' to observe the loaded page."
            }

        elif action == "open_app":
            app_name = text or arguments.get("name") or "browser"
            subprocess.Popen(f"start {app_name}", shell=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
            time.sleep(1.0)
            return {
                "status": "success",
                "action": "open_app",
                "name": app_name,
                "message": f"Launched application '{app_name}'. Call action='screenshot' to locate it on screen."
            }

        elif action == "wait":
            time.sleep(float(wait_sec or 1.0))
            return {"status": "success", "action": "wait", "seconds": wait_sec}

        else:
            return {"status": "error", "message": f"Unknown action '{action}'"}

    except Exception as e:
        logger.error(f"Desktop control failed for action '{action}': {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def register_desktop_automation_tools():
    tool_registry.register(tool_desktop_control, handle_desktop_control)
