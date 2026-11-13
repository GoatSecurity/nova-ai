import io
import os
import sys
import time
import base64
import ctypes
from typing import Dict, Any, Optional
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


def _get_screen_size():
    if sys.platform == "win32":
        try:
            u32 = ctypes.windll.user32
            return u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
        except Exception:
            return 1920, 1080
    return 1920, 1080


def _take_screenshot() -> Dict[str, Any]:
    w, h = _get_screen_size()
    try:
        from PIL import ImageGrab
        im = ImageGrab.grab()
        buf = io.BytesIO()
        if im.width > 1280:
            scale = 1280.0 / im.width
            im = im.resize((int(im.width * scale), int(im.height * scale)))
        im.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return {
            "status": "success",
            "action": "screenshot",
            "width": w,
            "height": h,
            "image_base64": b64,
            "mime_type": "image/png",
            "message": f"Captured desktop screen ({w}x{h})."
        }
    except Exception as e:
        return {
            "status": "warning",
            "action": "screenshot",
            "width": w,
            "height": h,
            "image_base64": None,
            "message": f"Screen capture attempted on desktop ({w}x{h}). Note: Interactive GUI session required for full frame grab. Details: {str(e)}"
        }


def _mouse_move(x: int, y: int):
    if sys.platform == "win32":
        ctypes.windll.user32.SetCursorPos(int(x), int(y))


def _mouse_click(x: Optional[int] = None, y: Optional[int] = None, button: str = "left", double: bool = False):
    if sys.platform == "win32":
        u32 = ctypes.windll.user32
        if x is not None and y is not None:
            u32.SetCursorPos(int(x), int(y))
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
        u32.SetCursorPos(int(start_x), int(start_y))
        time.sleep(0.04)
        u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.04)
        steps = 10
        for i in range(1, steps + 1):
            curr_x = int(start_x + (end_x - start_x) * (i / steps))
            curr_y = int(start_y + (end_y - start_y) * (i / steps))
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
            time.sleep(0.01)


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
        time.sleep(0.05)
        for vk in reversed(vks):
            u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


tool_desktop_control = BaseTool(
    name="desktop_control",
    description="Controls the desktop GUI environment using mouse and keyboard actions, and captures screenshots for visual inspection. Designed for vision-capable models to operate Windows applications, web browsers, Photoshop, etc.",
    category="system",
    risk_level="HIGH",
    requires_approval=False,
    parameters=[
        ToolParameter(
            name="action",
            type="string",
            description="The desktop action to perform: 'screenshot', 'click', 'double_click', 'right_click', 'move', 'drag', 'type', 'press_key', 'scroll', 'wait'.",
            enum=["screenshot", "click", "double_click", "right_click", "move", "drag", "type", "press_key", "scroll", "wait"]
        ),
        ToolParameter(name="x", type="integer", description="X coordinate on screen (0 to screen width)", required=False),
        ToolParameter(name="y", type="integer", description="Y coordinate on screen (0 to screen height)", required=False),
        ToolParameter(name="end_x", type="integer", description="Target X coordinate for drag operations", required=False),
        ToolParameter(name="end_y", type="integer", description="Target Y coordinate for drag operations", required=False),
        ToolParameter(name="text", type="string", description="Text to type using keyboard", required=False),
        ToolParameter(name="key", type="string", description="Key or key combination to press (e.g. 'enter', 'tab', 'win', 'ctrl+c', 'ctrl+v', 'alt+f4')", required=False),
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
    scroll_clicks = arguments.get("scroll_clicks")
    wait_sec = arguments.get("wait_seconds", 0.5)

    try:
        if action == "screenshot":
            return _take_screenshot()

        elif action == "click":
            _mouse_click(x, y, button="left", double=False)
            return {"status": "success", "action": "click", "x": x, "y": y, "message": f"Left clicked at ({x}, {y})"}

        elif action == "double_click":
            _mouse_click(x, y, button="left", double=True)
            return {"status": "success", "action": "double_click", "x": x, "y": y, "message": f"Double clicked at ({x}, {y})"}

        elif action == "right_click":
            _mouse_click(x, y, button="right", double=False)
            return {"status": "success", "action": "right_click", "x": x, "y": y, "message": f"Right clicked at ({x}, {y})"}

        elif action == "move":
            if x is not None and y is not None:
                _mouse_move(x, y)
                return {"status": "success", "action": "move", "x": x, "y": y, "message": f"Moved mouse to ({x}, {y})"}
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
            if text:
                _keyboard_type(text)
                return {"status": "success", "action": "type", "text": text}
            return {"status": "error", "message": "Missing text parameter to type"}

        elif action == "press_key":
            if key:
                _keyboard_press(key)
                return {"status": "success", "action": "press_key", "key": key}
            return {"status": "error", "message": "Missing key parameter"}

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
