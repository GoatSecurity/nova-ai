import pytest
from pathlib import Path
from backend.app.tools.registry import tool_registry
from backend.app.core.config import settings

@pytest.mark.asyncio
async def test_utility_tools():
    ctx = {"workspace_path": str(settings.BASE_DIR)}

    # Datetime tool
    res = await tool_registry.execute_tool("get_current_datetime", {}, ctx)
    assert "iso" in res
    assert "date" in res

    # Calculate tool
    calc_res = await tool_registry.execute_tool("calculate", {"expression": "10 * 10 + 42"}, ctx)
    assert calc_res["result"] == 142

@pytest.mark.asyncio
async def test_system_diagnostics_tools():
    ctx = {"workspace_path": str(settings.BASE_DIR)}

    # System info
    sys_res = await tool_registry.execute_tool("get_system_information", {}, ctx)
    assert "os" in sys_res
    assert "cpu_count_logical" in sys_res

    # OS info
    os_res = await tool_registry.execute_tool("get_os_information", {}, ctx)
    assert "system" in os_res

    # Memory usage
    mem_res = await tool_registry.execute_tool("inspect_memory_usage", {}, ctx)
    assert "ram" in mem_res
    assert "percent_used" in mem_res["ram"]

@pytest.mark.asyncio
async def test_filesystem_tools(tmp_path):
    ctx = {"workspace_path": str(tmp_path)}

    # Create file
    create_res = await tool_registry.execute_tool(
        "create_file",
        {"path": "sample.txt", "content": "Hello World\nLine 2\nLine 3"},
        ctx
    )
    assert create_res["status"] == "success"
    assert (tmp_path / "sample.txt").exists()

    # Read file
    read_res = await tool_registry.execute_tool(
        "read_file",
        {"path": "sample.txt", "max_lines": 2},
        ctx
    )
    assert read_res["total_lines"] == 3
    assert read_res["lines_returned"] == 2
    assert "Hello World" in read_res["content"]

    # Edit file with diff
    edit_res = await tool_registry.execute_tool(
        "edit_file",
        {"path": "sample.txt", "target": "Line 2", "replacement": "Updated Line 2"},
        ctx
    )
    assert edit_res["status"] == "success"
    assert "diff" in edit_res
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8").startswith("Hello World\nUpdated Line 2")

    # List directory
    list_res = await tool_registry.execute_tool("list_directory", {"path": str(tmp_path)}, ctx)
    assert list_res["total_items"] >= 1

    # Delete file
    del_res = await tool_registry.execute_tool("delete_file", {"path": "sample.txt"}, ctx)
    assert del_res["status"] == "success"
    assert not (tmp_path / "sample.txt").exists()
