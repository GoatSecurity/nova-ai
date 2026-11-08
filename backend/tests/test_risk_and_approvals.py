import pytest
from backend.app.execution.risk_engine import RiskEngine, RiskLevel
from backend.app.execution.approval import ApprovalManager
from backend.app.database.repositories.conversation_repo import ConversationRepository
from backend.app.database.repositories.execution_repo import ExecutionRepository

def test_risk_classification_rules():
    # LOW risk
    lvl, _ = RiskEngine.classify_command("Get-ChildItem -Path .")
    assert lvl == RiskLevel.LOW
    lvl, _ = RiskEngine.classify_command("dir")
    assert lvl == RiskLevel.LOW
    lvl, _ = RiskEngine.classify_command("systeminfo")
    assert lvl == RiskLevel.LOW

    # MODERATE risk
    lvl, _ = RiskEngine.classify_command("npm run build")
    assert lvl == RiskLevel.MODERATE

    # HIGH risk
    lvl, _ = RiskEngine.classify_command("Remove-Item -Force C:\\temp\\file.txt")
    assert lvl == RiskLevel.HIGH
    lvl, _ = RiskEngine.classify_command("Stop-Process -Id 1234")
    assert lvl == RiskLevel.HIGH

    # CRITICAL risk
    lvl, _ = RiskEngine.classify_command("format C:")
    assert lvl == RiskLevel.CRITICAL
    lvl, _ = RiskEngine.classify_command("Remove-Item -Recurse C:\\Windows")
    assert lvl == RiskLevel.CRITICAL

@pytest.mark.asyncio
async def test_approval_evaluation_modes():
    conv = await ConversationRepository.create_conversation(title="Approval Test")
    conv_id = conv["id"]

    # 1. LOW risk under allow_safe -> Auto allowed
    can_exec, app, reason = await ApprovalManager.evaluate_execution(
        conversation_id=conv_id,
        tool_call_id="tc_1",
        command="Get-Date",
        shell="powershell",
        cwd="C:\\",
        tool_name="get_current_datetime",
        permission_mode="allow_safe"
    )
    assert can_exec is True
    assert app is None

    # 2. MODERATE risk under allow_safe -> Approval required
    can_exec, app, reason = await ApprovalManager.evaluate_execution(
        conversation_id=conv_id,
        tool_call_id="tc_2",
        command="npm install some-package",
        shell="powershell",
        cwd="C:\\",
        tool_name="execute_powershell",
        permission_mode="allow_safe"
    )
    assert can_exec is False
    assert app is not None
    assert app["risk_level"] == "MODERATE"

    # 3. CRITICAL risk under ANY mode -> NEVER auto-approved
    can_exec, app_crit, _ = await ApprovalManager.evaluate_execution(
        conversation_id=conv_id,
        tool_call_id="tc_3",
        command="format D:",
        shell="cmd",
        cwd="C:\\",
        tool_name="execute_cmd",
        permission_mode="allow_safe"
    )
    assert can_exec is False
    assert app_crit["risk_level"] == "CRITICAL"

    # 4. Approve once
    decided = await ExecutionRepository.decide_approval(app["id"], "approved_once", "test_user")
    assert decided["status"] == "approved_once"

    # Verify approved command with exact hash
    verified = await ApprovalManager.verify_approved_command(
        approval_id=app["id"],
        command="npm install some-package",
        shell="powershell",
        cwd="C:\\"
    )
    assert verified is True

    # Tampering with command must invalidate approval!
    tampered = await ApprovalManager.verify_approved_command(
        approval_id=app["id"],
        command="npm install some-package && malicious_payload",
        shell="powershell",
        cwd="C:\\"
    )
    assert tampered is False, "Modified command payload must fail approval verification"

    await ConversationRepository.delete_conversation(conv_id)
