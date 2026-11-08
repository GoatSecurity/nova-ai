from typing import Optional, Dict
from backend.app.execution.process_manager import ProcessManager, ExecutionResult

class CMDExecutor:
    @staticmethod
    async def run(
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        execution_id: Optional[str] = None,
        env: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        return await ProcessManager.run_command(
            command=command,
            shell="cmd",
            cwd=cwd,
            timeout_seconds=timeout,
            execution_id=execution_id,
            env_vars=env
        )
