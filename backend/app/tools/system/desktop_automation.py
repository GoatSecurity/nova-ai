import io
import os
import sys
import time
import base64
import ctypes
import threading
import webbrowser
import subprocess
import urllib.parse
import difflib
from typing import Dict, Any, Optional, Tuple, List
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


def _get_process_name_by_pid(pid: int) -> str:
    """Returns the executable name for a given PID using Win32 API."""
    if sys.platform != "win32" or not pid:
        return ""
    try:
        kernel32 = ctypes.windll.kernel32
        h_proc = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h_proc:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(512)
            size = wintypes.DWORD(512)
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            kernel32.CloseHandle(h_proc)
    except Exception:
        pass
    return ""


def _list_all_windows(min_size: int = 50) -> List[Dict[str, Any]]:
    """Lists all visible top-level desktop windows with PID, process name, bounds, and active state."""
    if sys.platform != "win32":
        return []
    _attach_thread_to_input_desktop()
    user32 = ctypes.windll.user32
    active_hwnd = user32.GetForegroundWindow()
    windows = []

    def _enum_cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()

                if title and title != "Program Manager":
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top

                    if w >= min_size and h >= min_size:
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        pname = _get_process_name_by_pid(pid.value)
                        is_min = bool(user32.IsIconic(hwnd))

                        windows.append({
                            "hwnd": hwnd,
                            "title": title,
                            "process": pname,
                            "pid": pid.value,
                            "is_active": (hwnd == active_hwnd),
                            "is_minimized": is_min,
                            "rect": [rect.left, rect.top, w, h]
                        })
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)

    # Sort active window first, then by area descending
    windows.sort(key=lambda x: (not x["is_active"], -(x["rect"][2] * x["rect"][3])))
    return windows


def _find_window(query: str, windows: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """Smart window locator matching query against browser aliases, process names, or window titles."""
    if not query:
        return None
    if windows is None:
        windows = _list_all_windows()

    q_lower = str(query).lower().strip()

    # Browser alias matching
    browser_keywords = ("browser", "web", "internet", "web browser", "webbrowser", "\u0645\u0631\u0648\u0631\u06af\u0631")
    browser_processes = ("firefox.exe", "chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "vivaldi.exe")
    browser_titles = ("firefox", "chrome", "edge", "brave", "opera", "vivaldi", "google", "search")

    if any(bk in q_lower for bk in browser_keywords):
        for w in windows:
            p_lower = w["process"].lower()
            t_lower = w["title"].lower()
            if any(bp in p_lower for bp in browser_processes) or any(bt in t_lower for bt in browser_titles):
                if "nova workstation" not in t_lower:
                    return w

    # Direct match on process or title
    for w in windows:
        p_lower = w["process"].lower()
        t_lower = w["title"].lower()
        if "nova" not in q_lower and "nova workstation" in t_lower:
            continue
        if q_lower == p_lower or q_lower == os.path.splitext(p_lower)[0] or q_lower in t_lower:
            return w

    # Partial substring match
    for w in windows:
        p_lower = w["process"].lower()
        t_lower = w["title"].lower()
        if "nova" not in q_lower and "nova workstation" in t_lower:
            continue
        if any(term in p_lower or term in t_lower for term in q_lower.split()):
            return w

    return None


def _activate_window(hwnd: int) -> bool:
    """Robust Win32 window focus & activation bypassing Windows foreground locks."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        _attach_thread_to_input_desktop()
        user32.AllowSetForegroundWindow(0xFFFFFFFF)

        SW_RESTORE = 9
        SW_SHOW = 5
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd != hwnd:
            fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
            cur_thread = kernel32.GetCurrentThreadId()
            if fg_thread and cur_thread and fg_thread != cur_thread:
                user32.AttachThreadInput(cur_thread, fg_thread, True)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.AttachThreadInput(cur_thread, fg_thread, False)
            else:
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
        else:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)

        time.sleep(0.08)
        return True
    except Exception as e:
        logger.debug(f"Failed to activate window {hwnd}: {e}")
        return False


def _close_window(hwnd: int) -> bool:
    """Closes a window cleanly using WM_CLOSE."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        WM_CLOSE = 0x0010
        return bool(user32.PostMessageW(hwnd, WM_CLOSE, 0, 0))
    except Exception:
        return False


def _open_or_focus_browser(target_url: Optional[str] = None) -> Dict[str, Any]:
    """Finds existing open browser or launches default browser, focuses it, and captures screen."""
    bw = _find_window("browser")
    if bw:
        _activate_window(bw["hwnd"])
        if target_url:
            webbrowser.open(target_url)
            time.sleep(1.0)
            _activate_window(bw["hwnd"])
        else:
            time.sleep(0.3)
        shot = _take_screenshot()
        res = {
            "status": "success",
            "action": "open_browser",
            "browser": bw["title"],
            "process": bw["process"],
            "message": f"Focused open browser '{bw['title']}' ({bw['process']}). Browser window is active."
        }
        if shot.get("image_base64"):
            res["image_base64"] = shot["image_base64"]
            res["screen_width"] = shot.get("screen_width")
            res["screen_height"] = shot.get("screen_height")
            res["frame_width"] = shot.get("frame_width")
            res["frame_height"] = shot.get("frame_height")
        return res

    # No open browser: launch default
    url = target_url or "https://www.google.com"
    webbrowser.open(url)
    time.sleep(1.5)
    new_bw = _find_window("browser")
    if new_bw:
        _activate_window(new_bw["hwnd"])

    shot = _take_screenshot()
    res = {
        "status": "success",
        "action": "open_browser",
        "url": url,
        "message": f"Launched default browser with '{url}'. Browser window is active."
    }
    if shot.get("image_base64"):
        res["image_base64"] = shot["image_base64"]
        res["screen_width"] = shot.get("screen_width")
        res["screen_height"] = shot.get("screen_height")
        res["frame_width"] = shot.get("frame_width")
        res["frame_height"] = shot.get("frame_height")
    return res


def _search_in_browser(query: str, suppress_screenshot: bool = False) -> Dict[str, Any]:
    """Instant 1-turn Google search: opens Google search URL and brings browser window to front."""
    if not query:
        return {"status": "error", "message": "Missing search query"}

    target_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
    webbrowser.open(target_url)
    time.sleep(1.2)

    bw = _find_window("browser")
    if bw:
        _activate_window(bw["hwnd"])

    res = {
        "status": "success",
        "action": "search",
        "query": query,
        "url": target_url,
        "message": f"Searched for '{query}' in browser via Google. Results are active and displayed."
    }
    if not suppress_screenshot:
        shot = _take_screenshot()
        if shot.get("image_base64"):
            res["image_base64"] = shot["image_base64"]
            res["screen_width"] = shot.get("screen_width")
            res["screen_height"] = shot.get("screen_height")
            res["frame_width"] = shot.get("frame_width")
            res["frame_height"] = shot.get("frame_height")
    return res


def _open_or_focus_app(app_name: str, suppress_screenshot: bool = False) -> Dict[str, Any]:
    """Focuses app if already open, or launches it and brings to front."""
    if not app_name:
        return {"status": "error", "message": "Missing app name"}

    # Special handling for browser
    if app_name.lower().strip() in ("browser", "web", "internet"):
        return _open_or_focus_browser()

    existing = _find_window(app_name)
    if existing:
        _activate_window(existing["hwnd"])
        time.sleep(0.4)
        res = {
            "status": "success",
            "action": "open_app",
            "name": app_name,
            "window": existing["title"],
            "process": existing["process"],
            "message": f"App '{app_name}' is already running ('{existing['title']}'). Brought to foreground."
        }
        if not suppress_screenshot:
            shot = _take_screenshot()
            if shot.get("image_base64"):
                res["image_base64"] = shot["image_base64"]
                res["screen_width"] = shot.get("screen_width")
                res["screen_height"] = shot.get("screen_height")
                res["frame_width"] = shot.get("frame_width")
                res["frame_height"] = shot.get("frame_height")
        return res

    # Not running: launch
    subprocess.Popen(f"start {app_name}", shell=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    time.sleep(1.5)
    new_win = _find_window(app_name)
    if new_win:
        _activate_window(new_win["hwnd"])

    res = {
        "status": "success",
        "action": "open_app",
        "name": app_name,
        "message": f"Launched application '{app_name}'."
    }
    if not suppress_screenshot:
        shot = _take_screenshot()
        if shot.get("image_base64"):
            res["image_base64"] = shot["image_base64"]
            res["screen_width"] = shot.get("screen_width")
            res["screen_height"] = shot.get("screen_height")
            res["frame_width"] = shot.get("frame_width")
            res["frame_height"] = shot.get("frame_height")
    return res


def _handle_focus_window(target: str, suppress_screenshot: bool = False) -> Dict[str, Any]:
    """Brings the specified window to the foreground."""
    if not target:
        return {"status": "error", "message": "Missing target window name or process"}

    target_clean = str(target).lower().strip()
    if target_clean in ("browser", "web", "internet", "\u0645\u0631\u0648\u0631\u06af\u0631"):
        return _open_or_focus_browser()

    w = _find_window(target_clean)
    if not w:
        all_wins = _list_all_windows()
        available = [f"'{win['title']}' ({win['process']})" for win in all_wins[:6]]
        return {
            "status": "warning",
            "action": "focus_window",
            "target": target,
            "found": False,
            "message": f"Window matching '{target}' was not found. Open windows: {', '.join(available)}"
        }

    _activate_window(w["hwnd"])
    time.sleep(0.3)
    res = {
        "status": "success",
        "action": "focus_window",
        "target": target,
        "matched_window": w,
        "message": f"Brought '{w['title']}' ({w['process']}) to foreground."
    }
    if not suppress_screenshot:
        shot = _take_screenshot()
        if shot.get("image_base64"):
            res["image_base64"] = shot["image_base64"]
            res["screen_width"] = shot.get("screen_width")
            res["screen_height"] = shot.get("screen_height")
            res["frame_width"] = shot.get("frame_width")
            res["frame_height"] = shot.get("frame_height")
    return res


def _bring_window_to_foreground(target_name: Optional[str] = None) -> bool:
    """Compatibility wrapper: brings window matching target_name to foreground."""
    if not target_name:
        return True
    w = _find_window(target_name)
    if w:
        return _activate_window(w["hwnd"])
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

    # Downscale to max 1024 dimension for lightning-fast tokenization and low prefill latency
    MAX_DIM = 1024
    frame_w = im.width
    frame_h = im.height
    if frame_w > MAX_DIM or frame_h > MAX_DIM:
        scale = min(MAX_DIM / float(frame_w), MAX_DIM / float(frame_h))
        frame_w = max(1, int(im.width * scale))
        frame_h = max(1, int(im.height * scale))
        im = im.resize((frame_w, frame_h), Image.Resampling.LANCZOS)

    _last_frame_info = {
        "screen_w": w,
        "screen_h": h,
        "frame_w": frame_w,
        "frame_h": frame_h
    }

    buf = io.BytesIO()
    im.convert("RGB").save(buf, format="JPEG", quality=75, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "status": "success",
        "action": "screenshot",
        "screen_width": w,
        "screen_height": h,
        "frame_width": frame_w,
        "frame_height": frame_h,
        "image_base64": b64,
        "mime_type": "image/jpeg",
        "message": f"Captured desktop screen. Screen: {w}x{h}, Visual frame: {frame_w}x{frame_h}. Coordinates you specify will be automatically mapped to physical screen pixels."
    }


def _ocr_screen(query: Optional[str] = None, auto_click: bool = False, double_click: bool = False) -> Dict[str, Any]:
    """Runs RapidOCR on current visual frame to find UI buttons, text elements, and exact coordinates."""
    global _last_frame_info
    im = _capture_raw_screen_image()
    if im is None:
        return {"status": "error", "message": "Failed to capture desktop screen for OCR."}

    w, h = im.size
    MAX_DIM = 1024
    frame_w, frame_h = w, h
    if frame_w > MAX_DIM or frame_h > MAX_DIM:
        scale = min(MAX_DIM / float(frame_w), MAX_DIM / float(frame_h))
        frame_w = max(1, int(w * scale))
        frame_h = max(1, int(h * scale))
        im = im.resize((frame_w, frame_h), Image.Resampling.LANCZOS)

    _last_frame_info = {
        "screen_w": w,
        "screen_h": h,
        "frame_w": frame_w,
        "frame_h": frame_h
    }

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
        scored_matches = []
        for it in items:
            t_clean = it["text"].lower()
            # Prevent accidental match of NOVA workstation UI elements when searching for target apps
            if "nova" not in q_clean and ("nova workstation" in t_clean or "ask anything, @" in t_clean):
                continue

            if t_clean == q_clean:
                sim = 1.0
            elif q_clean in t_clean:
                sim = 0.80 + (len(q_clean) / max(len(t_clean), 1)) * 0.15
            elif t_clean in q_clean and len(t_clean) >= 3 and (len(t_clean) / len(q_clean) >= 0.35):
                sim = 0.70 + (len(t_clean) / len(q_clean)) * 0.15
            else:
                sim = difflib.SequenceMatcher(None, q_clean, t_clean).ratio()

            if sim >= 0.55:
                match_dict = dict(it)
                match_dict["similarity"] = round(sim, 3)
                scored_matches.append(match_dict)

        scored_matches.sort(key=lambda x: (x["similarity"], x["score"]), reverse=True)

        if not scored_matches:
            return {
                "status": "warning",
                "action": "find_text",
                "query": query,
                "found": False,
                "screen_width": w,
                "screen_height": h,
                "message": f"Text '{query}' was not found on screen. {len(items)} other text elements were detected."
            }

        best = scored_matches[0]
        result = {
            "status": "success",
            "action": "find_text",
            "query": query,
            "found": True,
            "best_match": best,
            "all_matches": scored_matches[:5],
            "total_matches": len(scored_matches),
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


def _init_win32_clipboard():
    if sys.platform == "win32":
        try:
            u32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32
            u32.OpenClipboard.argtypes = [wintypes.HWND]
            u32.OpenClipboard.restype = wintypes.BOOL
            u32.EmptyClipboard.argtypes = []
            u32.EmptyClipboard.restype = wintypes.BOOL
            u32.CloseClipboard.argtypes = []
            u32.CloseClipboard.restype = wintypes.BOOL
            u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
            u32.SetClipboardData.restype = wintypes.HANDLE
            u32.GetClipboardData.argtypes = [wintypes.UINT]
            u32.GetClipboardData.restype = wintypes.HANDLE

            k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            k32.GlobalAlloc.restype = wintypes.HGLOBAL
            k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            k32.GlobalLock.restype = wintypes.LPVOID
            k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            k32.GlobalUnlock.restype = wintypes.BOOL
        except Exception:
            pass

_init_win32_clipboard()


def _set_clipboard_text(text: str) -> bool:
    if sys.platform != "win32":
        return False
    try:
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        for _ in range(8):
            if u32.OpenClipboard(0):
                break
            time.sleep(0.02)
        else:
            return False

        try:
            u32.EmptyClipboard()
            encoded = text.encode("utf-16le") + b"\x00\x00"
            GMEM_MOVEABLE = 0x0002
            CF_UNICODETEXT = 13
            h_mem = k32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            if not h_mem:
                return False
            ptr = k32.GlobalLock(h_mem)
            if not ptr:
                return False
            ctypes.memmove(ptr, encoded, len(encoded))
            k32.GlobalUnlock(h_mem)
            return bool(u32.SetClipboardData(CF_UNICODETEXT, h_mem))
        finally:
            u32.CloseClipboard()
    except Exception as e:
        logger.debug(f"Failed to set clipboard text: {e}")
        return False


def _get_clipboard_text() -> str:
    if sys.platform != "win32":
        return ""
    try:
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        CF_UNICODETEXT = 13
        for _ in range(5):
            if u32.OpenClipboard(0):
                break
            time.sleep(0.02)
        else:
            return ""
        try:
            h = u32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return ""
            ptr = k32.GlobalLock(h)
            if not ptr:
                return ""
            val = ctypes.wstring_at(ptr)
            k32.GlobalUnlock(h)
            return val
        finally:
            u32.CloseClipboard()
    except Exception as e:
        logger.debug(f"Failed to get clipboard text: {e}")
        return ""


def _keyboard_type(text: str):
    if sys.platform == "win32":
        u32 = ctypes.windll.user32
        # On Windows, keybd_event truncates 16-bit scan codes to 8-bit BYTE (code & 0xFF),
        # which garbles Unicode/Persian text (e.g. 0x0633 & 0xFF == 0x33 '3', turning Persian text into corrupt ASCII).
        # Using CF_UNICODETEXT clipboard paste ensures 100% faithful Unicode typing and immunity to active keyboard layout.
        has_unicode = any(ord(c) > 127 for c in text)
        if has_unicode or len(text) > 3:
            old_clip = _get_clipboard_text()
            if _set_clipboard_text(text):
                time.sleep(0.04)
                _keyboard_press("ctrl+v")
                time.sleep(0.08)
                if old_clip:
                    def _restore():
                        time.sleep(0.6)
                        _set_clipboard_text(old_clip)
                    threading.Thread(target=_restore, daemon=True).start()
                return

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
    description="Enterprise-grade desktop GUI environment control using mouse, keyboard, window management, and screen OCR element detection. Designed for vision-capable models to operate Windows applications, web browsers, Photoshop, IDEs, etc. Supports 1-turn instant search ('search'), window focus/activation ('focus_window'), process enumeration ('list_windows'), composite macro execution ('batch'), and finding UI elements by text label ('find_text').",
    category="system",
    risk_level="HIGH",
    requires_approval=False,
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="The desktop action to perform: 'search' (instant 1-turn web search in default browser), 'focus_window' (brings target window to foreground by app/process/title or 'browser'), 'list_windows' (enumerates all open windows and titles), 'open_browser' (opens or focuses browser), 'open_app' (launches app or focuses if already open), 'open_url' (navigates browser to URL), 'batch' (executes multiple steps sequentially in 1 call), 'find_text' (locates text/buttons with OCR and optionally clicks), 'ocr' (scans screen and lists all UI text elements with coordinates), 'screenshot', 'click', 'double_click', 'right_click', 'middle_click', 'move', 'drag', 'type', 'press_key', 'scroll', 'close_window', 'wait'.",
            enum=[
                "search", "focus_window", "list_windows", "open_browser", "open_app", "open_url", "batch",
                "find_text", "ocr", "screenshot", "click", "double_click", "right_click", "middle_click",
                "move", "drag", "type", "press_key", "scroll", "close_window", "wait"
            ]
        ),
        ToolParameter(name="text", type="string", description="Text to type using keyboard, query for 'search', window title/process for 'focus_window', text to search for in 'find_text', URL for 'open_url', or app name for 'open_app'", required=False),
        ToolParameter(name="steps", type="array", description="List of step dictionaries to execute in a single batch call. Each step has 'action', 'text', 'key', 'x', 'y', 'wait_seconds', etc.", required=False),
        ToolParameter(name="key", type="string", description="Key or key combination to press (e.g. 'enter', 'tab', 'win', 'win+r', 'alt+d', 'ctrl+l', 'ctrl+t', 'ctrl+c', 'ctrl+v', 'alt+f4', 'alt+tab')", required=False),
        ToolParameter(name="x", type="integer", description="X coordinate on screen (0 to screen width) or on visual frame. If provided to 'type', clicks at (x, y) first to focus before typing.", required=False),
        ToolParameter(name="y", type="integer", description="Y coordinate on screen (0 to screen height) or on visual frame. If provided to 'type', clicks at (x, y) first to focus before typing.", required=False),
        ToolParameter(name="end_x", type="integer", description="Target X coordinate for drag operations", required=False),
        ToolParameter(name="end_y", type="integer", description="Target Y coordinate for drag operations", required=False),
        ToolParameter(name="click", type="boolean", description="Whether to automatically click the found text element when action='find_text'", required=False),
        ToolParameter(name="double_click", type="boolean", description="Whether to double click instead of single click when action='find_text'", required=False),
        ToolParameter(name="press_enter", type="boolean", description="Whether to press Enter after typing text", required=False),
        ToolParameter(name="clear_first", type="boolean", description="Whether to clear existing text (Ctrl+A, Backspace) before typing", required=False),
        ToolParameter(name="scroll_clicks", type="integer", description="Scroll amount: positive to scroll up, negative to scroll down", required=False),
        ToolParameter(name="wait_seconds", type="number", description="Seconds to pause/wait (e.g. 1.0)", required=False)
    ]
)

ACTION_ALIASES = {
    # wait
    "wait": "wait",
    "wait_seconds": "wait",
    "sleep": "wait",
    "delay": "wait",
    "pause": "wait",
    # press_key
    "press_key": "press_key",
    "key_press": "press_key",
    "press": "press_key",
    "hotkey": "press_key",
    "shortcut": "press_key",
    "key": "press_key",
    # type
    "type": "type",
    "write": "type",
    "input": "type",
    "input_text": "type",
    "send_keys": "type",
    # click
    "click": "click",
    "left_click": "click",
    "click_mouse": "click",
    # double_click
    "double_click": "double_click",
    "dbl_click": "double_click",
    # right_click
    "right_click": "right_click",
    "context_menu": "right_click",
    # middle_click
    "middle_click": "middle_click",
    # move
    "move": "move",
    "mouse_move": "move",
    "hover": "move",
    # drag
    "drag": "drag",
    "mouse_drag": "drag",
    "drag_and_drop": "drag",
    # scroll
    "scroll": "scroll",
    "mouse_scroll": "scroll",
    "wheel": "scroll",
    # screenshot
    "screenshot": "screenshot",
    "capture_screen": "screenshot",
    "screen": "screenshot",
    # find_text
    "find_text": "find_text",
    "click_text": "find_text",
    "find": "find_text",
    "find_and_click": "find_text",
    # ocr
    "ocr": "ocr",
    "scan_screen": "ocr",
    "read_screen": "ocr",
    # window management
    "list_windows": "list_windows",
    "get_windows": "list_windows",
    "windows": "list_windows",
    "focus_window": "focus_window",
    "activate_window": "focus_window",
    "switch_window": "focus_window",
    "bring_to_front": "focus_window",
    "close_window": "close_window",
    "close_app": "close_window",
    # browser actions
    "search": "search",
    "search_browser": "search",
    "google_search": "search",
    "web_search": "search",
    "open_browser": "open_browser",
    "browser": "open_browser",
    "focus_browser": "open_browser",
    "open_url": "open_url",
    "navigate": "open_url",
    "go_to_url": "open_url",
    # apps
    "open_app": "open_app",
    "launch_app": "open_app",
    "start_app": "open_app",
    "run_app": "open_app",
    # batch
    "batch": "batch",
    "macro": "batch",
    "sequence": "batch",
    "steps": "batch",
}


async def _execute_single_action(arguments: Dict[str, Any], suppress_screenshot: bool = False) -> Dict[str, Any]:
    raw_action = (arguments.get("action") or "").lower().strip()
    action = ACTION_ALIASES.get(raw_action, raw_action)

    x = arguments.get("x")
    y = arguments.get("y")
    end_x = arguments.get("end_x")
    end_y = arguments.get("end_y")
    text = (
        arguments.get("text")
        or arguments.get("query")
        or arguments.get("title")
        or arguments.get("name")
        or arguments.get("url")
        or arguments.get("input")
    )
    key = arguments.get("key") or arguments.get("keys") or arguments.get("combo")
    click_flag = bool(arguments.get("click", False))
    double_click_flag = bool(arguments.get("double_click", False))
    press_enter = bool(arguments.get("press_enter", False))
    clear_first = bool(arguments.get("clear_first", False))
    scroll_clicks = arguments.get("scroll_clicks")

    if action == "search":
        return _search_in_browser(text or "", suppress_screenshot=suppress_screenshot)

    elif action == "focus_window":
        return _handle_focus_window(text or "", suppress_screenshot=suppress_screenshot)

    elif action == "list_windows":
        wins = _list_all_windows()
        return {
            "status": "success",
            "action": "list_windows",
            "total_windows": len(wins),
            "windows": wins,
            "message": f"Found {len(wins)} open visible windows."
        }

    elif action == "close_window":
        if not text:
            return {"status": "error", "message": "Missing window title or process name to close"}
        w = _find_window(text)
        if not w:
            return {"status": "warning", "action": "close_window", "target": text, "found": False, "message": f"Window '{text}' was not found"}
        closed = _close_window(w["hwnd"])
        return {
            "status": "success" if closed else "error",
            "action": "close_window",
            "target": text,
            "closed": closed,
            "message": f"Closed window '{w['title']}' ({w['process']})" if closed else f"Failed to send WM_CLOSE to '{w['title']}'"
        }

    elif action == "open_browser":
        return _open_or_focus_browser(text)

    elif action == "open_app":
        return _open_or_focus_app(text or "", suppress_screenshot=suppress_screenshot)

    elif action == "open_url":
        target_url = text or arguments.get("url")
        if not target_url:
            return {"status": "error", "message": "Missing url or text parameter for open_url"}
        if not (target_url.startswith("http://") or target_url.startswith("https://")):
            target_url = "https://" + target_url
        return _open_or_focus_browser(target_url)

    elif action == "find_text":
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

    elif action == "middle_click":
        _mouse_click(x, y, button="middle", double=False)
        mx, my = _map_coords(x, y)
        return {"status": "success", "action": "middle_click", "screen_x": mx, "screen_y": my, "message": f"Middle clicked at ({mx}, {my})"}

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

        if x is not None and y is not None:
            _mouse_click(x, y, button="left", double=False)
            time.sleep(0.12)

        if clear_first:
            _keyboard_press("ctrl+a")
            time.sleep(0.04)
            _keyboard_press("backspace")
            time.sleep(0.04)

        _keyboard_type(str(text))

        if press_enter:
            time.sleep(0.08)
            _keyboard_press("enter")
            time.sleep(0.8)
            res = {
                "status": "success",
                "action": "type",
                "text": text,
                "clicked_at": [x, y] if (x is not None and y is not None) else None,
                "pressed_enter": True,
                "message": f"Typed '{text}' and pressed Enter."
            }
            if not suppress_screenshot:
                shot = _take_screenshot()
                if shot.get("image_base64"):
                    res["image_base64"] = shot["image_base64"]
                    res["screen_width"] = shot.get("screen_width")
                    res["screen_height"] = shot.get("screen_height")
                    res["frame_width"] = shot.get("frame_width")
                    res["frame_height"] = shot.get("frame_height")
            return res

        return {
            "status": "success",
            "action": "type",
            "text": text,
            "clicked_at": [x, y] if (x is not None and y is not None) else None,
            "pressed_enter": False
        }

    elif action == "press_key":
        key_name = key or arguments.get("key") or arguments.get("text")
        if key_name:
            _keyboard_press(str(key_name))
            return {"status": "success", "action": "press_key", "key": key_name}
        return {"status": "error", "message": "Missing key parameter"}

    elif action == "wait":
        raw_dur = (
            arguments.get("wait_seconds")
            or arguments.get("seconds")
            or arguments.get("duration")
            or arguments.get("text")
            or 0.5
        )
        try:
            sec = float(raw_dur)
        except (ValueError, TypeError):
            sec = 0.5
        time.sleep(sec)
        return {"status": "success", "action": "wait", "seconds": sec}

    else:
        return {"status": "error", "message": f"Unknown action '{raw_action}'"}


async def handle_desktop_control(arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    raw_action = (arguments.get("action") or "").lower().strip()
    action = ACTION_ALIASES.get(raw_action, raw_action)
    try:
        if action == "batch":
            steps = arguments.get("steps") or arguments.get("actions") or []
            if not steps or not isinstance(steps, list):
                return {"status": "error", "message": "Missing or invalid 'steps' parameter for batch action. Provide a list of step dictionaries."}

            executed_steps = []
            for idx, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                step_raw = (step.get("action") or "").lower().strip()
                sub_res = await _execute_single_action(step, suppress_screenshot=True)
                executed_steps.append({
                    "step": idx + 1,
                    "action": step_raw,
                    "status": sub_res.get("status", "unknown"),
                    "details": sub_res.get("message") or sub_res
                })
                # Safety pause between rapid physical actions if specified
                step_wait = step.get("wait_seconds") or step.get("seconds") or 0.05
                try:
                    sw = float(step_wait)
                    if sw > 0:
                        time.sleep(sw)
                except Exception:
                    pass

            final_shot = _take_screenshot()
            res = {
                "status": "success",
                "action": "batch",
                "total_steps": len(executed_steps),
                "steps_completed": executed_steps,
                "message": f"Batch automation completed {len(executed_steps)} actions successfully. Final screen state is attached."
            }
            if final_shot.get("image_base64"):
                res["image_base64"] = final_shot["image_base64"]
                res["screen_width"] = final_shot.get("screen_width")
                res["screen_height"] = final_shot.get("screen_height")
                res["frame_width"] = final_shot.get("frame_width")
                res["frame_height"] = final_shot.get("frame_height")
            return res

        return await _execute_single_action(arguments, suppress_screenshot=False)

    except Exception as e:
        logger.error(f"Desktop control failed for action '{raw_action}': {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def register_desktop_automation_tools():
    tool_registry.register(tool_desktop_control, handle_desktop_control)
