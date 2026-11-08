import os
import sys
import time
import asyncio
import tempfile
import difflib
import subprocess
from pathlib import Path
from typing import Dict, Any, List
from backend.app.tools.base import BaseTool, ToolParameter
from backend.app.tools.registry import tool_registry
from backend.app.execution.process_manager import ProcessManager
from backend.app.core.config import settings
from backend.app.core.logging import audit_log
from backend.app.core.security import (
    is_protected_nova_core_path,
    command_targets_nova_core_mutation,
    python_code_targets_nova_core_mutation,
)

tool_run_python = BaseTool(
    name="run_python",
    description="Executes a Python snippet or script file directly in the active environment and returns stdout/stderr.",
    category="development",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="code", type="string", description="Python code to execute", required=False),
        ToolParameter(name="script_path", type="string", description="Path to .py script file to run", required=False),
        ToolParameter(name="args", type="string", description="Optional CLI arguments", required=False)
    ]
)

tool_run_script = BaseTool(
    name="run_script",
    description="Executes a development build/test script (npm, pip, pytest, cargo, etc.).",
    category="development",
    risk_level="MODERATE",
    requires_approval=True,
    parameters=[
        ToolParameter(name="command", type="string", description="The command to execute (e.g. 'npm run build', 'pytest')"),
        ToolParameter(name="cwd", type="string", description="Working directory", required=False)
    ]
)

tool_inspect_project = BaseTool(
    name="inspect_project",
    description="Detects project framework, package managers (package.json, pyproject.toml, requirements.txt, cargo), and git status.",
    category="development",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="path", type="string", description="Project root directory", required=False)
    ]
)

tool_search_code = BaseTool(
    name="search_code",
    description="Searches for exact text or regex across code files in the workspace.",
    category="development",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="query", type="string", description="Text or pattern to search"),
        ToolParameter(name="file_extension", type="string", description="Optional extension filter, e.g. '.py', '.ts'", required=False),
        ToolParameter(name="limit", type="integer", description="Max matches (default 30)", required=False, default=30)
    ]
)

tool_apply_patch = BaseTool(
    name="apply_file_patch",
    description="Applies a unified diff patch to a source file.",
    category="development",
    risk_level="MODERATE",
    requires_approval=True,
    parameters=[
        ToolParameter(name="path", type="string", description="File to patch"),
        ToolParameter(name="patch_content", type="string", description="Unified diff patch text")
    ]
)

tool_run_tests = BaseTool(
    name="run_tests",
    description="Runs automated test suite (pytest or npm test) and parses pass/fail statistics.",
    category="development",
    risk_level="MODERATE",
    requires_approval=False,
    parameters=[
        ToolParameter(name="test_runner", type="string", description="'pytest' or 'npm'", required=False, default="pytest", enum=["pytest", "npm"]),
        ToolParameter(name="test_target", type="string", description="Specific test file or folder", required=False)
    ]
)

# --- Handlers ---

async def handle_run_python(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    code = args.get("code")
    script_path = args.get("script_path")
    cli_args_raw = args.get("args", "")
    cwd = ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE
    timeout = int(args.get("timeout") or settings.DEFAULT_EXECUTION_TIMEOUT)

    if not code and not script_path:
        return {"error": "Must provide either 'code' or 'script_path'."}

    if code:
        blocked_py, reason_py = python_code_targets_nova_core_mutation(code, cwd=cwd)
        if blocked_py:
            audit_log("CORE_SELF_MODIFICATION_BLOCKED", "system", {"tool": "run_python", "reason": reason_py})
            return {"error": reason_py, "exit_code": 1}
    if script_path:
        script_full = Path(cwd) / script_path if not Path(script_path).is_absolute() else Path(script_path)
        blocked_sp, reason_sp = is_protected_nova_core_path(script_full)
        if blocked_sp:
            audit_log("CORE_SELF_MODIFICATION_BLOCKED", "system", {"tool": "run_python", "script_path": str(script_full)})
            return {"error": reason_sp, "exit_code": 1}

    split_args = [a for a in cli_args_raw.split() if a] if isinstance(cli_args_raw, str) else []
    temp_file = None
    start_time = time.perf_counter()

    try:
        if code:
            # Create a dedicated temp script file in utf-8 to avoid shell quote mangling
            fd, temp_file = tempfile.mkstemp(suffix=".py", prefix="nova_run_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(code)
            py_bin = sys.executable.strip('\'"')
            exec_args = [py_bin, temp_file] + split_args
        else:
            target = Path(cwd) / script_path if not Path(script_path).is_absolute() else Path(script_path)
            if not target.exists():
                return {"error": f"Script file not found: {target}", "exit_code": 1}
            py_bin = sys.executable.strip('\'"')
            exec_args = [py_bin, str(target)] + split_args

        custom_env = os.environ.copy()
        custom_env["PYTHONIOENCODING"] = "utf-8"
        custom_env["PYTHONUNBUFFERED"] = "1"

        proc = await asyncio.create_subprocess_exec(
            *exec_args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=custom_env
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(timeout)
            )
            timed_out = False
        except asyncio.TimeoutError:
            timed_out = True
            try:
                proc.kill()
                stdout_bytes, stderr_bytes = await proc.communicate()
            except Exception:
                stdout_bytes, stderr_bytes = b"", b"Execution timed out."

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        stderr_str = stderr_bytes.decode("utf-8", errors="replace")

        return {
            "exit_code": proc.returncode if not timed_out else 124,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "duration_ms": duration_ms,
            "timed_out": timed_out
        }
    except Exception as e:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Python execution error: {str(e)}",
            "duration_ms": duration_ms,
            "timed_out": False
        }
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass

async def handle_run_script(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    cmd = args.get("command", "")
    cwd = args.get("cwd") or ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE
    blocked_cmd, reason_cmd = command_targets_nova_core_mutation(cmd, cwd=cwd)
    if blocked_cmd:
        audit_log("CORE_SELF_MODIFICATION_BLOCKED", "system", {"tool": "run_script", "command": cmd})
        return {"error": reason_cmd, "exit_code": 1, "stdout": "", "stderr": reason_cmd, "duration_ms": 0, "timed_out": False}
    native_shell = "powershell" if sys.platform.startswith("win") else ("zsh" if sys.platform == "darwin" else "bash")
    res = await ProcessManager.run_command(command=cmd, shell=native_shell, cwd=cwd)
    return {
        "exit_code": res.exit_code,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "duration_ms": res.duration_ms,
        "timed_out": res.timed_out
    }

async def handle_inspect_project(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    root_str = args.get("path") or ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE
    root = Path(root_str).resolve()
    if not root.exists():
        return {"error": f"Path '{root}' not found."}

    indicators = {
        "has_package_json": (root / "package.json").exists(),
        "has_pyproject_toml": (root / "pyproject.toml").exists(),
        "has_requirements_txt": (root / "requirements.txt").exists(),
        "has_git": (root / ".git").exists(),
        "has_cargo_toml": (root / "Cargo.toml").exists(),
        "has_dockerfile": (root / "Dockerfile").exists(),
        "has_vite_config": (root / "vite.config.ts").exists() or (root / "vite.config.js").exists(),
    }

    project_type = "generic"
    if indicators["has_package_json"] and indicators["has_vite_config"]:
        project_type = "react-vite-web"
    elif indicators["has_package_json"]:
        project_type = "node-js"
    elif indicators["has_pyproject_toml"] or indicators["has_requirements_txt"]:
        project_type = "python"
    elif indicators["has_cargo_toml"]:
        project_type = "rust"

    return {
        "project_root": str(root),
        "detected_type": project_type,
        "features": indicators
    }

async def handle_search_code(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query", "")
    ext = args.get("file_extension")
    limit = args.get("limit", 30)
    root = Path(ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE)

    if not query:
        return {"error": "Query cannot be empty."}

    results = []
    ignored_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

    for root_dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for f in files:
            if ext and not f.endswith(ext):
                continue
            file_path = Path(root_dir) / f
            try:
                for enc in ("utf-8", "latin-1"):
                    try:
                        content = file_path.read_text(encoding=enc)
                        break
                    except Exception:
                        continue
                else:
                    continue

                if query.lower() in content.lower():
                    lines = content.splitlines()
                    for idx, line in enumerate(lines):
                        if query.lower() in line.lower():
                            results.append({
                                "file": str(file_path.relative_to(root)),
                                "line_number": idx + 1,
                                "line_text": line.strip()[:150]
                            })
                            if len(results) >= limit:
                                return {"query": query, "matches": results, "count": len(results)}
            except Exception:
                continue

    return {"query": query, "matches": results, "count": len(results)}

async def handle_apply_patch(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    # Placeholder patch handler using edit_file logic
    ws = ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE
    raw_p = args.get("path", "")
    target_path = (Path(ws) / raw_p).resolve() if not Path(raw_p).is_absolute() else Path(raw_p).resolve()
    blocked_p, reason_p = is_protected_nova_core_path(target_path)
    if blocked_p:
        audit_log("CORE_SELF_MODIFICATION_BLOCKED", "system", {"tool": "apply_file_patch", "path": str(target_path)})
        return {"error": reason_p}
    return {"status": "info", "message": "For patch modifications, prefer using edit_file with precise target and replacement blocks."}

async def handle_run_tests(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    runner = args.get("test_runner", "pytest")
    target = args.get("test_target", "")
    cwd = ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE

    if runner == "npm":
        cmd = f"npm test {target}".strip()
    else:
        cmd = f'python -m pytest {target} --tb=short'.strip()

    native_shell = "powershell" if sys.platform.startswith("win") else ("zsh" if sys.platform == "darwin" else "bash")
    res = await ProcessManager.run_command(command=cmd, shell=native_shell, cwd=cwd)
    passed = "passed" in res.stdout.lower() and res.exit_code == 0
    return {
        "runner": runner,
        "exit_code": res.exit_code,
        "passed": passed,
        "stdout": res.stdout,
        "stderr": res.stderr
    }

def register_development_tools():
    tool_registry.register(tool_run_python, handle_run_python)
    tool_registry.register(tool_run_script, handle_run_script)
    tool_registry.register(tool_inspect_project, handle_inspect_project)
    tool_registry.register(tool_search_code, handle_search_code)
    tool_registry.register(tool_apply_patch, handle_apply_patch)
    tool_registry.register(tool_run_tests, handle_run_tests)
