import pytest
from backend.app.tools.registry import tool_registry

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
async def test_desktop_control_mouse_and_key():
    # Test mouse move
    res_move = await tool_registry.execute_tool("desktop_control", {"action": "move", "x": 100, "y": 100}, {})
    assert res_move.get("status") == "success"

    # Test click
    res_click = await tool_registry.execute_tool("desktop_control", {"action": "click", "x": 100, "y": 100}, {})
    assert res_click.get("status") == "success"

    # Test typing
    res_type = await tool_registry.execute_tool("desktop_control", {"action": "type", "text": "hello"}, {})
    assert res_type.get("status") == "success"
