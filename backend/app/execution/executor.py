import os
from typing import Dict, Any, Optional, Tuple
from backend.app.execution.process_manager import ProcessManager, ExecutionResult
from backend.app.execution.approval import ApprovalManager
from backend.app.database.repositories.execution_repo import ExecutionRepository
from backend.app.core.security import (
    sanitize_untrusted_text,
    validate_workspace_path,
    command_targets_nova_core_mutation,
)
from backend.app.core.logging import audit_log, logger
from backend.app.core.config import settings

class ExecutionCoordinator:
    @staticmethod
    async def execute_tool_request(
        conversation_id: str,
        tool_call_id: str,
        tool_name: str,
        command: str,
        shell: str = "powershell",
        cwd: Optional[str] = None,
        permission_mode: str = "allow_safe",
        pre_approved_id: Optional[str] = None
    ) -> Tuple[bool, ExecutionResult, Optional[Dict[str, Any]]]:
        """
        Executes an OS command request through the full security pipeline.
        Returns: (success, ExecutionResult, approval_record_if_waiting)
        """
        work_dir = cwd or settings.DEFAULT_WORKSPACE

        # 0. Hard block on ANY command attempting to alter NOVA's core codebase (even if pre-approved)
        is_core_mod, core_block_msg = command_targets_nova_core_mutation(command, cwd=work_dir)
        if is_core_mod:
            res = ExecutionResult(
                command=command,
                shell=shell,
                cwd=work_dir,
                stdout="",
                stderr=core_block_msg,
                exit_code=1,
                duration_ms=0,
            )
            audit_log(
                "CORE_SELF_MODIFICATION_BLOCKED",
                "system",
                {"conversation_id": conversation_id, "tool_name": tool_name, "command": command, "cwd": work_dir},
            )
            return False, res, None

        # 1. Workspace boundary validation (if not absolute system path)
        is_valid, resolved_path, err = validate_workspace_path(work_dir, settings.DEFAULT_WORKSPACE)
        if not is_valid:
            # We allow system paths if user specifically requested, but log warning
            logger.info(f"Command cwd '{work_dir}' is outside default workspace.")

        # 2. Check if pre-approved via approval ID
        if pre_approved_id:
            verified = await ApprovalManager.verify_approved_command(
                approval_id=pre_approved_id,
                command=command,
                shell=shell,
                cwd=work_dir
            )
            if not verified:
                res = ExecutionResult(
                    command=command,
                    shell=shell,
                    cwd=work_dir,
                    stdout="",
                    stderr="Execution halted: Command integrity verification failed. Command does not match approval hash.",
                    exit_code=1,
                    duration_ms=0
                )
                audit_log("APPROVAL_INTEGRITY_MISMATCH", "system", {"approval_id": pre_approved_id, "command": command})
                return False, res, None
        else:
            # 3. Permission Evaluation
            can_execute, approval, reason = await ApprovalManager.evaluate_execution(
                conversation_id=conversation_id,
                tool_call_id=tool_call_id,
                command=command,
                shell=shell,
                cwd=work_dir,
                tool_name=tool_name,
                permission_mode=permission_mode
            )
            if not can_execute:
                # Waiting for approval
                res = ExecutionResult(
                    command=command,
                    shell=shell,
                    cwd=work_dir,
                    stdout="",
                    stderr=f"WAITING_FOR_USER_APPROVAL: {reason}",
                    exit_code=0,
                    duration_ms=0
                )
                return False, res, approval

        # 4. Execute the command
        audit_log("EXECUTION_START", "agent", {
            "conversation_id": conversation_id,
            "tool_call_id": tool_call_id,
            "command": command,
            "shell": shell,
            "cwd": work_dir
        })

        result = await ProcessManager.run_command(
            command=command,
            shell=shell,
            cwd=work_dir,
            execution_id=tool_call_id
        )

        # 5. Result Sanitization (guard against prompt injection in tool outputs)
        sanitized_stdout = sanitize_untrusted_text(result.stdout)
        sanitized_stderr = sanitize_untrusted_text(result.stderr)
        result.stdout = sanitized_stdout
        result.stderr = sanitized_stderr

        # 6. Ensure tool call record exists before recording result
        existing_tc = await ExecutionRepository.get_tool_call(tool_call_id)
        if not existing_tc:
            await ExecutionRepository.create_tool_call(
                message_id="msg_direct",
                conversation_id=conversation_id,
                tool_name=tool_name,
                arguments={"command": command, "shell": shell, "cwd": work_dir},
                risk_level="LOW",
                status="running",
                tool_call_id=tool_call_id
            )

        # Record tool result in database
        is_error = (result.exit_code != 0) or result.timed_out or result.cancelled
        await ExecutionRepository.record_tool_result(
            tool_call_id=tool_call_id,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            is_error=is_error,
            output_data={"timed_out": result.timed_out, "cancelled": result.cancelled, "truncated": result.truncated}
        )

        audit_log("EXECUTION_COMPLETE", "system", {
            "conversation_id": conversation_id,
            "tool_call_id": tool_call_id,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms
        })

        return (not is_error), result, None
