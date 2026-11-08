import os
import sys
import time
import asyncio
from typing import Dict, Optional, Tuple, Callable
from pydantic import BaseModel
from backend.app.core.config import settings
from backend.app.core.logging import logger

class ExecutionResult(BaseModel):
    command: str
    shell: str
    cwd: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    timed_out: bool = False
    cancelled: bool = False
    truncated: bool = False

class ProcessManager:
    """
    Manages asynchronous local process execution on Windows, tracking active jobs
    and supporting clean cancellation and timeout enforcement.
    """
    _active_processes: Dict[str, asyncio.subprocess.Process] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def cancel_execution(cls, execution_id: str) -> bool:
        async with cls._lock:
            proc = cls._active_processes.get(execution_id)
            if proc:
                try:
                    proc.terminate()
                    # Wait briefly then kill if still running
                    await asyncio.sleep(0.2)
                    if proc.returncode is None:
                        proc.kill()
                    return True
                except Exception as e:
                    logger.warning(f"Error terminating process {execution_id}: {e}")
            return False

    @classmethod
    async def run_command(
        cls,
        command: str,
        shell: str = "powershell",
        cwd: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        execution_id: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None
    ) -> ExecutionResult:
        work_dir = cwd or settings.DEFAULT_WORKSPACE
        timeout = timeout_seconds or settings.DEFAULT_EXECUTION_TIMEOUT
        exec_id = execution_id or f"exec_{int(time.time() * 1000)}"

        # Prepare invocation args with cross-platform OS detection
        is_win = sys.platform.startswith("win")
        shell_lower = shell.lower()

        if shell_lower in ("bash", "sh", "zsh") or (not is_win and shell_lower in ("powershell", "pwsh", "cmd", "shell")):
            chosen_shell = os.environ.get("SHELL") or ("/bin/zsh" if sys.platform == "darwin" else "/bin/bash")
            if not os.path.exists(chosen_shell):
                chosen_shell = "/bin/sh"
            executable = chosen_shell
            args = [executable, "-c", command]
        elif shell_lower in ("powershell", "pwsh"):
            if not is_win:
                import shutil
                pwsh_bin = shutil.which("pwsh") or shutil.which("powershell")
                if pwsh_bin:
                    executable = pwsh_bin
                    args = [executable, "-NoProfile", "-NonInteractive", "-Command", command]
                else:
                    chosen_shell = os.environ.get("SHELL") or "/bin/bash"
                    executable = chosen_shell if os.path.exists(chosen_shell) else "/bin/sh"
                    args = [executable, "-c", command]
            else:
                ps_prelude = (
                    "$ProgressPreference = 'SilentlyContinue'; "
                    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13; "
                    "$PSDefaultParameterValues['Invoke-WebRequest:UseBasicParsing'] = $true; "
                    "$PSDefaultParameterValues['Invoke-RestMethod:UseBasicParsing'] = $true; "
                    "Remove-Item alias:curl -ErrorAction SilentlyContinue; "
                    "Remove-Item alias:wget -ErrorAction SilentlyContinue; "
                )
                executable = "powershell.exe"
                args = [
                    executable,
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-Command", f"{ps_prelude}{command}"
                ]
        elif shell_lower == "cmd":
            if not is_win:
                chosen_shell = os.environ.get("SHELL") or "/bin/bash"
                executable = chosen_shell if os.path.exists(chosen_shell) else "/bin/sh"
                args = [executable, "-c", command]
            else:
                executable = "cmd.exe"
                args = [executable, "/c", command]
        elif shell_lower == "python":
            executable = sys.executable
            args = [executable, "-c", command]
        else:
            args = command.split()

        custom_env = os.environ.copy()
        custom_env["PYTHONIOENCODING"] = "utf-8"
        custom_env["PYTHONUNBUFFERED"] = "1"
        if env_vars:
            custom_env.update(env_vars)

        start_time = time.perf_counter()
        timed_out = False
        cancelled = False
        truncated = False

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=custom_env
            )

            async with cls._lock:
                cls._active_processes[exec_id] = process

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=float(timeout)
                )
            except asyncio.TimeoutError:
                timed_out = True
                try:
                    process.terminate()
                    await asyncio.sleep(0.3)
                    if process.returncode is None:
                        process.kill()
                    stdout_bytes, stderr_bytes = await process.communicate()
                except Exception:
                    stdout_bytes, stderr_bytes = b"", b"Execution timed out."

            except asyncio.CancelledError:
                cancelled = True
                try:
                    process.terminate()
                    await asyncio.sleep(0.2)
                    if process.returncode is None:
                        process.kill()
                except Exception:
                    pass
                stdout_bytes, stderr_bytes = b"", b"Execution cancelled by user."

        except Exception as err:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ExecutionResult(
                command=command,
                shell=shell,
                cwd=work_dir,
                stdout="",
                stderr=f"Process launch error: {str(err)}",
                exit_code=1,
                duration_ms=duration_ms,
                timed_out=False,
                cancelled=False,
                truncated=False
            )
        finally:
            async with cls._lock:
                cls._active_processes.pop(exec_id, None)

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Multi-encoding decode fallback
        def safe_decode(raw: bytes) -> str:
            for enc in ("utf-8", "cp1252", "cp850", "cp437", "latin-1"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")

        stdout_str = safe_decode(stdout_bytes)
        stderr_str = safe_decode(stderr_bytes)

        # Output capping
        if len(stdout_str) > settings.MAX_OUTPUT_BYTES:
            stdout_str = stdout_str[:settings.MAX_OUTPUT_BYTES] + f"\n\n[OUTPUT TRUNCATED: Exceeded {settings.MAX_OUTPUT_BYTES} bytes limit]"
            truncated = True

        if len(stderr_str) > settings.MAX_OUTPUT_BYTES:
            stderr_str = stderr_str[:settings.MAX_OUTPUT_BYTES] + f"\n\n[STDERR TRUNCATED: Exceeded limit]"
            truncated = True

        exit_code = process.returncode if process.returncode is not None else (124 if timed_out else 1)

        return ExecutionResult(
            command=command,
            shell=shell,
            cwd=work_dir,
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=exit_code,
            duration_ms=duration_ms,
            timed_out=timed_out,
            cancelled=cancelled,
            truncated=truncated
        )
