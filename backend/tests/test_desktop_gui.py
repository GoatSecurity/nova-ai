import pytest
from backend.app.tools.registry import tool_registry
from backend.app.tools.system.desktop_automation import _take_screenshot, _map_coords, _get_screen_size

@pytest.mark.asyncio
async def test_desktop_control_registered():
    tool = tool_registry.get_tool("desktop_control")
    assert tool is not None
    assert tool.name == "desktop_control"
    assert tool.category == "system"

    # Test wait action
    res = await tool_registry.execute_tool("desktop_control", {"action": "wait", "wait_seconds": 0.01}, {})
    assert res.get("status") == "success"
    assert res.get("action") == "wait"

@pytest.mark.asyncio
async def test_desktop_control_screenshot_and_mapping():
    # Test screenshot
    shot = _take_screenshot()
    assert shot.get("status") == "success"
    assert shot.get("action") == "screenshot"
    assert shot.get("image_base64") is not None
    assert shot.get("screen_width", 0) > 0
    assert shot.get("screen_height", 0) > 0

    # Test coordinate mapping
    sw, sh = _get_screen_size()
    rx, ry = _map_coords(100, 100)
    assert 0 <= rx < sw
    assert 0 <= ry < sh

    # Test normalized coordinates (0.5, 0.5)
    nx, ny = _map_coords(0.5, 0.5)
    assert nx == int(sw * 0.5)
    assert ny == int(sh * 0.5)

@pytest.mark.asyncio
async def test_desktop_control_mouse_and_key():
    # Test mouse move
    res_move = await tool_registry.execute_tool("desktop_control", {"action": "move", "x": 100, "y": 100}, {})
    assert res_move.get("status") == "success"

    # Test click
    res_click = await tool_registry.execute_tool("desktop_control", {"action": "click", "x": 100, "y": 100}, {})
    assert res_click.get("status") == "success"

    # Test typing with coordinates
    res_type = await tool_registry.execute_tool(
        "desktop_control",
        {"action": "type", "text": "test", "x": 100, "y": 100, "press_enter": False},
        {}
    )
    assert res_type.get("status") == "success"
    assert res_type.get("text") == "test"
    assert res_type.get("clicked_at") == [100, 100]

@pytest.mark.asyncio
async def test_desktop_control_ocr_and_find_text():
    # Test OCR scan
    res_ocr = await tool_registry.execute_tool("desktop_control", {"action": "ocr"}, {})
    assert res_ocr.get("status") in ("success", "error")
    if res_ocr.get("status") == "success":
        assert "elements" in res_ocr
        assert "total_elements" in res_ocr

    # Test find_text query
    res_find = await tool_registry.execute_tool(
        "desktop_control",
        {"action": "find_text", "text": "NonExistentDummyTargetXYZ", "click": False},
        {}
    )
    assert res_find.get("status") in ("warning", "error")
    assert res_find.get("query") == "NonExistentDummyTargetXYZ"

def test_strip_raw_tool_calls():
    from backend.app.agent.orchestrator import _strip_raw_tool_calls

    # Test fenced code block
    fenced = """Here is my plan:
```json
{
  "tool_call": {
    "name": "web_search",
    "arguments": {"query": "Iran news"}
  }
}
```
Here is the real answer."""
    assert _strip_raw_tool_calls(fenced) == "Here is my plan:\n\nHere is the real answer."

    # Test XML tool call
    xml_tool = """Analysis complete.
<tool_call>
{"name": "fetch_web_page", "arguments": {"url": "https://test.com"}}
</tool_call>
Have a great day!"""
    assert _strip_raw_tool_calls(xml_tool) == "Analysis complete.\n\nHave a great day!"

    # Test pure tool call with no text
    pure = """```json
{
  "tool_call": {
    "name": "desktop_control",
    "arguments": {"action": "click", "x": 100, "y": 100}
  }
}
```"""
    assert _strip_raw_tool_calls(pure) == ""
