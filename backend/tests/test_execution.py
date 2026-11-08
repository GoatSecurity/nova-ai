import pytest
from backend.app.execution.process_manager import ProcessManager

@pytest.mark.asyncio
async def test_powershell_execution():
    res = await ProcessManager.run_command(
        command="Write-Output 'NOVA_PWSH_TEST'",
        shell="powershell"
    )
    assert res.exit_code == 0
    assert "NOVA_PWSH_TEST" in res.stdout
    assert res.duration_ms >= 0
    assert res.timed_out is False

@pytest.mark.asyncio
async def test_cmd_execution():
    res = await ProcessManager.run_command(
        command="echo NOVA_CMD_TEST",
        shell="cmd"
    )
    assert res.exit_code == 0
    assert "NOVA_CMD_TEST" in res.stdout

@pytest.mark.asyncio
async def test_execution_timeout():
    # Test timeout with 1 second cap
    res = await ProcessManager.run_command(
        command="Start-Sleep -Seconds 10",
        shell="powershell",
        timeout_seconds=1
    )
    assert res.timed_out is True
