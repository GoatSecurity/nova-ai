from typing import Dict, Any, Tuple, Optional
from backend.app.execution.risk_engine import RiskEngine, RiskLevel
from backend.app.database.repositories.execution_repo import ExecutionRepository
from backend.app.core.security import calculate_command_hash
from backend.app.core.logging import audit_log, logger

class ApprovalManager:
    @staticmethod
    async def evaluate_execution(
        conversation_id: str,
        tool_call_id: str,
        command: str,
        shell: str,
        cwd: str,
        tool_name: str,
        permission_mode: str = "allow_safe"
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Evaluates whether a command needs approval or can execute immediately.
        Returns: (can_execute, approval_record, reason)
        """
        risk_level, explanation = RiskEngine.classify_command(command, shell)
        cmd_hash = calculate_command_hash(command, shell, cwd)

        # 1. Critical operations can NEVER be auto-approved
        if risk_level == RiskLevel.CRITICAL:
            audit_log("CRITICAL_OPERATION_BLOCKED_WAITING_APPROVAL", "system", {
                "conversation_id": conversation_id,
                "command": command,
                "cwd": cwd
            })
            approval = await ExecutionRepository.create_approval_request(
                conversation_id=conversation_id,
                tool_call_id=tool_call_id,
                command_hash=cmd_hash,
                command=command,
                shell=shell,
                cwd=cwd,
                risk_level=risk_level.value
            )
            return False, approval, f"Critical risk detected: {explanation}"

        # 2. Check Permission Mode: ask_every_time or manual
        if permission_mode in ("ask_every_time", "manual"):
            approval = await ExecutionRepository.create_approval_request(
                conversation_id=conversation_id,
                tool_call_id=tool_call_id,
                command_hash=cmd_hash,
                command=command,
                shell=shell,
                cwd=cwd,
                risk_level=risk_level.value
            )
            return False, approval, f"Approval mode '{permission_mode}' requires user authorization"

        # 3. Check Session Permissions
        has_session_grant = await ExecutionRepository.check_session_permission(
            conversation_id=conversation_id,
            tool_name=tool_name,
            cwd=cwd
        )
        if has_session_grant and risk_level in (RiskLevel.LOW, RiskLevel.MODERATE):
            return True, None, "Allowed under active session permission grant"

        # 4. Mode: allow_safe
        if permission_mode == "allow_safe":
            if risk_level == RiskLevel.LOW:
                return True, None, "Allowed automatically (Safe read-only operation)"
            else:
                approval = await ExecutionRepository.create_approval_request(
                    conversation_id=conversation_id,
                    tool_call_id=tool_call_id,
                    command_hash=cmd_hash,
                    command=command,
                    shell=shell,
                    cwd=cwd,
                    risk_level=risk_level.value
                )
                return False, approval, f"{risk_level.value} risk operation requires approval"

        # Conservative fallback: require approval
        approval = await ExecutionRepository.create_approval_request(
            conversation_id=conversation_id,
            tool_call_id=tool_call_id,
            command_hash=cmd_hash,
            command=command,
            shell=shell,
            cwd=cwd,
            risk_level=risk_level.value
        )
        return False, approval, "Fallback safety: approval required"

    @staticmethod
    async def verify_approved_command(
        approval_id: str,
        command: str,
        shell: str,
        cwd: str
    ) -> bool:
        """
        Guarantees that the command being executed matches the exact integrity hash approved.
        """
        app = await ExecutionRepository.get_approval(approval_id)
        if not app:
            return False
        if app["status"] not in ("approved_once", "approved_session"):
            return False
            
        current_hash = calculate_command_hash(command, shell, cwd)
        return current_hash == app["command_hash"]
