import pytest
from pathlib import Path
from backend.app.core.config import settings
from backend.app.tools.registry import tool_registry
from backend.app.execution.executor import ExecutionCoordinator


@pytest.mark.asyncio
async def test_core_codebase_cannot_be_modified_by_file_tools(tmp_path):
    base = Path(settings.BASE_DIR).resolve()
    ctx = {"workspace_path": str(settings.SCRATCH_DIR)}

    # Attempt to create a file inside backend/
    res_create = await tool_registry.execute_tool(
        "create_file",
        {"path": str(base / "backend" / "injected.py"), "content": "print('hack')", "overwrite": True},
        ctx,
    )
    assert "error" in res_create
    assert "SECURITY POLICY BLOCKED" in res_create["error"]
    assert not (base / "backend" / "injected.py").exists()

    # Attempt to edit orchestrator.py
    res_edit = await tool_registry.execute_tool(
        "edit_file",
        {"path": str(base / "backend" / "app" / "agent" / "orchestrator.py"), "target": "import json", "replacement": "import os"},
        ctx,
    )
    assert "error" in res_edit
    assert "SECURITY POLICY BLOCKED" in res_edit["error"]

    # Attempt to delete main.py or entire BASE_DIR
    res_del = await tool_registry.execute_tool("delete_file", {"path": str(base / "backend" / "app" / "main.py")}, ctx)
    assert "error" in res_del
    assert "SECURITY POLICY BLOCKED" in res_del["error"]
    assert (base / "backend" / "app" / "main.py").exists()

    res_del_root = await tool_registry.execute_tool("delete_file", {"path": str(base), "recursive": True}, ctx)
    assert "error" in res_del_root
    assert "SECURITY POLICY BLOCKED" in res_del_root["error"]

    # Attempt to move or copy into frontend/
    sample = tmp_path / "demo.js"
    sample.write_text("console.log(1);", encoding="utf-8")
    res_copy = await tool_registry.execute_tool(
        "copy_file",
        {"source_path": str(sample), "destination_path": str(base / "frontend" / "injected.js")},
        ctx,
    )
    assert "error" in res_copy
    assert "SECURITY POLICY BLOCKED" in res_copy["error"]
    assert not (base / "frontend" / "injected.js").exists()

    # Read-only inspection of NOVA files remains allowed
    res_read = await tool_registry.execute_tool(
        "read_file",
        {"path": str(base / "backend" / "app" / "core" / "config.py"), "max_lines": 5},
        ctx,
    )
    assert "content" in res_read and "error" not in res_read

    # Writing inside user's scratch/<project>/backend/ remains allowed!
    scratch_proj_file = Path(settings.SCRATCH_DIR) / "_pytest_core_guard_demo" / "backend" / "ok.py"
    try:
        res_ok = await tool_registry.execute_tool(
            "create_file",
            {"path": str(scratch_proj_file), "content": "x = 1\n", "overwrite": True},
            ctx,
        )
        assert res_ok.get("status") == "success"
        assert scratch_proj_file.exists()
    finally:
        if scratch_proj_file.parent.parent.exists():
            import shutil
            shutil.rmtree(scratch_proj_file.parent.parent, ignore_errors=True)


@pytest.mark.asyncio
async def test_core_codebase_blocked_in_python_and_shell_even_if_preapproved():
    base = Path(settings.BASE_DIR).resolve()
    ctx = {"workspace_path": str(settings.SCRATCH_DIR)}

    # Block run_python writing into backend/
    res_py = await tool_registry.execute_tool(
        "run_python",
        {"code": f"open(r'{base / 'backend' / 'hack.py'}', 'w').write('x')"},
        ctx,
    )
    assert "error" in res_py
    assert "SECURITY POLICY BLOCKED" in res_py["error"]

    # Block shell mutation via ExecutionCoordinator even with fake pre_approved_id bypass attempt
    ok, exec_res, approval = await ExecutionCoordinator.execute_tool_request(
        conversation_id="test-conv",
        tool_call_id="test-tc",
        tool_name="execute_powershell",
        command=f"Set-Content -Path '{base / 'frontend' / 'dist' / 'index.html'}' -Value 'hacked'",
        shell="powershell",
        cwd=str(settings.SCRATCH_DIR),
        permission_mode="session_approval",
        pre_approved_id="pretend-approved-id",
    )
    assert not ok
    assert approval is None
    assert "SECURITY POLICY BLOCKED" in exec_res.stderr
