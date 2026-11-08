import os
import sys
import platform
import psutil
from backend.app.execution.process_manager import ProcessManager
from typing import Dict, Any
from backend.app.tools.base import BaseTool, ToolParameter
from backend.app.tools.registry import tool_registry
from backend.app.execution.executor import ExecutionCoordinator
from backend.app.core.config import settings

# 1. execute_command / execute_powershell / execute_cmd
tool_execute_ps = BaseTool(
    name="execute_powershell",
    description="Executes a PowerShell script or command in Windows with full output capture.",
    category="system",
    risk_level="MODERATE",
    requires_approval=True,
    parameters=[
        ToolParameter(name="command", type="string", description="The PowerShell script/command to run"),
        ToolParameter(name="cwd", type="string", description="Optional working directory", required=False)
    ]
)

tool_execute_cmd = BaseTool(
    name="execute_cmd",
    description="Executes a Windows Command Prompt (CMD) command with output capture.",
    category="system",
    risk_level="MODERATE",
    requires_approval=True,
    parameters=[
        ToolParameter(name="command", type="string", description="The CMD command to run"),
        ToolParameter(name="cwd", type="string", description="Optional working directory", required=False)
    ]
)

tool_execute_generic = BaseTool(
    name="execute_command",
    description="Executes an operating system command using the native shell (PowerShell/CMD on Windows, Bash/Zsh on Linux & macOS).",
    category="system",
    risk_level="MODERATE",
    requires_approval=True,
    parameters=[
        ToolParameter(name="command", type="string", description="The command to execute"),
        ToolParameter(name="shell", type="string", description="Shell type: 'powershell', 'cmd', 'bash', 'zsh', or 'sh' (auto-detected if omitted)", required=False, enum=["powershell", "cmd", "bash", "zsh", "sh"]),
        ToolParameter(name="cwd", type="string", description="Working directory", required=False)
    ]
)

# 2. System Diagnostics (Read-only -> LOW risk, no approval required in allow_safe)
tool_sys_info = BaseTool(
    name="get_system_information",
    description="Returns detailed CPU, memory, OS platform, and architecture information.",
    category="system",
    risk_level="LOW",
    requires_approval=False,
    parameters=[]
)

tool_os_info = BaseTool(
    name="get_os_information",
    description="Returns operating system release, kernel/build version, hostname, and architecture (Windows, macOS, or Linux).",
    category="system",
    risk_level="LOW",
    requires_approval=False,
    parameters=[]
)

tool_processes = BaseTool(
    name="get_running_processes",
    description="Returns a list of currently running processes with PID, name, memory, and CPU usage.",
    category="system",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="limit", type="integer", description="Maximum number of processes to return (default 25)", required=False, default=25),
        ToolParameter(name="sort_by", type="string", description="Sort by 'memory' or 'cpu'", required=False, default="memory", enum=["memory", "cpu"])
    ]
)

tool_services = BaseTool(
    name="inspect_services",
    description="Inspects OS services/daemons and their status across Windows (Get-Service), Linux (systemd), and macOS (launchctl).",
    category="system",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="filter_name", type="string", description="Optional service name filter", required=False)
    ]
)

tool_env = BaseTool(
    name="inspect_environment",
    description="Returns current process environment variables and paths (sanitizes sensitive tokens).",
    category="system",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="variable_name", type="string", description="Specific environment variable to query", required=False)
    ]
)

tool_network = BaseTool(
    name="inspect_network_configuration",
    description="Inspects network interfaces, IP addresses, and DNS configuration.",
    category="system",
    risk_level="LOW",
    requires_approval=False,
    parameters=[]
)

tool_disk = BaseTool(
    name="inspect_disk_usage",
    description="Returns disk partition sizes, free space, and usage percentage for system drives.",
    category="system",
    risk_level="LOW",
    requires_approval=False,
    parameters=[]
)

tool_memory = BaseTool(
    name="inspect_memory_usage",
    description="Returns real-time RAM and swap memory usage statistics.",
    category="system",
    risk_level="LOW",
    requires_approval=False,
    parameters=[]
)

# --- Handlers ---

async def handle_execute_powershell(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    cmd = args.get("command", "")
    cwd = args.get("cwd") or ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE
    conv_id = ctx.get("conversation_id", "default")
    call_id = ctx.get("tool_call_id", "tc_direct")
    mode = ctx.get("permission_mode", settings.DEFAULT_PERMISSION_MODE)
    pre_app_id = ctx.get("pre_approved_id")

    success, result, approval = await ExecutionCoordinator.execute_tool_request(
        conversation_id=conv_id,
        tool_call_id=call_id,
        tool_name="execute_powershell",
        command=cmd,
        shell="powershell",
        cwd=cwd,
        permission_mode=mode,
        pre_approved_id=pre_app_id
    )

    if approval:
        return {
            "status": "waiting_approval",
            "approval_id": approval["id"],
            "risk_level": approval["risk_level"],
            "command": cmd,
            "message": "This operation requires user approval before execution."
        }

    return {
        "status": "completed" if success else "failed",
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out
    }

async def handle_execute_cmd(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    cmd = args.get("command", "")
    cwd = args.get("cwd") or ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE
    conv_id = ctx.get("conversation_id", "default")
    call_id = ctx.get("tool_call_id", "tc_direct")
    mode = ctx.get("permission_mode", settings.DEFAULT_PERMISSION_MODE)
    pre_app_id = ctx.get("pre_approved_id")

    success, result, approval = await ExecutionCoordinator.execute_tool_request(
        conversation_id=conv_id,
        tool_call_id=call_id,
        tool_name="execute_cmd",
        command=cmd,
        shell="cmd",
        cwd=cwd,
        permission_mode=mode,
        pre_approved_id=pre_app_id
    )

    if approval:
        return {
            "status": "waiting_approval",
            "approval_id": approval["id"],
            "risk_level": approval["risk_level"],
            "command": cmd,
            "message": "This operation requires user approval before execution."
        }

    return {
        "status": "completed" if success else "failed",
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out
    }

async def handle_execute_generic(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    default_shell = "powershell" if sys.platform.startswith("win") else ("zsh" if sys.platform == "darwin" else "bash")
    shell = (args.get("shell") or default_shell).lower()
    if shell == "cmd":
        return await handle_execute_cmd(args, ctx)
    if shell in ("bash", "zsh", "sh"):
        cmd = args.get("command", "")
        cwd = args.get("cwd") or ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE
        conv_id = ctx.get("conversation_id", "default")
        call_id = ctx.get("tool_call_id", "tc_direct")
        mode = ctx.get("permission_mode", settings.DEFAULT_PERMISSION_MODE)
        pre_app_id = ctx.get("pre_approved_id")

        success, result, approval = await ExecutionCoordinator.execute_tool_request(
            conversation_id=conv_id,
            tool_call_id=call_id,
            tool_name="execute_command",
            command=cmd,
            shell=shell,
            cwd=cwd,
            permission_mode=mode,
            pre_approved_id=pre_app_id,
        )
        if approval:
            return {
                "status": "waiting_approval",
                "approval_id": approval["id"],
                "risk_level": approval["risk_level"],
                "command": cmd,
                "message": "This operation requires user approval before execution.",
            }
        return {
            "status": "completed" if success else "failed",
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
        }
    return await handle_execute_powershell(args, ctx)

async def handle_sys_info(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    vm = psutil.virtual_memory()
    return {
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "total_ram_gb": round(vm.total / (1024**3), 2),
        "available_ram_gb": round(vm.available / (1024**3), 2),
        "python_version": platform.python_version()
    }

async def handle_os_info(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "system": platform.system(),
        "node_name": platform.node(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "platform": platform.platform()
    }

async def handle_processes(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    limit = args.get("limit", 25)
    sort_by = args.get("sort_by", "memory")
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
        try:
            mem_mb = round(p.info['memory_info'].rss / (1024 * 1024), 1) if p.info['memory_info'] else 0
            procs.append({
                "pid": p.info['pid'],
                "name": p.info['name'],
                "memory_mb": mem_mb,
                "cpu_percent": p.info['cpu_percent'] or 0.0
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if sort_by == "cpu":
        procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
    else:
        procs.sort(key=lambda x: x["memory_mb"], reverse=True)

    return {"count": len(procs), "processes": procs[:limit]}

async def handle_services(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    import json
    filter_name = (args.get("filter_name") or "").strip()

    if sys.platform.startswith("win"):
        cmd = "Get-Service"
        if filter_name:
            safe_f = filter_name.replace("'", "")
            cmd += f" -Name '*{safe_f}*'"
        cmd += " | Select-Object -First 30 Name, DisplayName, Status, StartType | ConvertTo-Json"
        from backend.app.execution.powershell import PowerShellExecutor
        res = await PowerShellExecutor.run(cmd)
        try:
            data = json.loads(res.stdout) if res.stdout.strip() else []
            return {"os": "windows", "services": data if isinstance(data, list) else [data]}
        except Exception:
            return {"os": "windows", "output": res.stdout, "error": res.stderr}

    if sys.platform == "darwin":
        res = await ProcessManager.run_command("launchctl list", shell="zsh", timeout_seconds=15)
        rows = []
        for line in res.stdout.splitlines()[1:]:
            parts = line.split(None, 2)
            if len(parts) == 3:
                name = parts[2]
                if not filter_name or filter_name.lower() in name.lower():
                    rows.append({"pid": parts[0], "status": parts[1], "name": name})
        return {"os": "macos", "services": rows[:30], **({"error": res.stderr} if res.exit_code != 0 else {})}

    # Linux (systemd / service)
    res = await ProcessManager.run_command(
        "systemctl list-units --type=service --all --no-pager --plain --no-legend",
        shell="bash",
        timeout_seconds=15,
    )
    rows = []
    for line in res.stdout.splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4:
            name = parts[0]
            if not filter_name or filter_name.lower() in name.lower():
                rows.append({
                    "name": name,
                    "load": parts[1],
                    "active": parts[2],
                    "sub": parts[3],
                    "description": parts[4] if len(parts) > 4 else "",
                })
    return {"os": "linux", "services": rows[:30], **({"error": res.stderr} if res.exit_code != 0 and not rows else {})}

async def handle_env(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    var_name = args.get("variable_name")
    if var_name:
        val = os.environ.get(var_name, "")
        # mask sensitive
        if any(s in var_name.upper() for s in ["KEY", "SECRET", "TOKEN", "PASS"]):
            val = "••••••••"
        return {"variable": var_name, "value": val}

    # return public env vars
    safe_env = {}
    for k, v in os.environ.items():
        if any(s in k.upper() for s in ["KEY", "SECRET", "TOKEN", "PASS", "CREDENTIAL"]):
            safe_env[k] = "••••••••"
        else:
            safe_env[k] = v[:200]
    return {"environment": safe_env}

async def handle_network(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    nics = psutil.net_if_addrs()
    result = {}
    for nic, addrs in nics.items():
        addr_list = []
        for a in addrs:
            addr_list.append({"family": str(a.family), "address": a.address, "netmask": a.netmask})
        result[nic] = addr_list
    return {"interfaces": result}

async def handle_disk(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    parts = psutil.disk_partitions()
    disks = []
    for p in parts:
        try:
            usage = psutil.disk_usage(p.mountpoint)
            disks.append({
                "device": p.device,
                "mountpoint": p.mountpoint,
                "fstype": p.fstype,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent_used": usage.percent
            })
        except Exception:
            continue
    return {"disks": disks}

async def handle_memory(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
    return {
        "ram": {
            "total_gb": round(vm.total / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
            "percent_used": vm.percent
        },
        "swap": {
            "total_gb": round(sm.total / (1024**3), 2),
            "used_gb": round(sm.used / (1024**3), 2),
            "free_gb": round(sm.free / (1024**3), 2),
            "percent_used": sm.percent
        }
    }

def register_system_tools():
    tool_registry.register(tool_execute_ps, handle_execute_powershell)
    tool_registry.register(tool_execute_cmd, handle_execute_cmd)
    tool_registry.register(tool_execute_generic, handle_execute_generic)
    tool_registry.register(tool_sys_info, handle_sys_info)
    tool_registry.register(tool_os_info, handle_os_info)
    tool_registry.register(tool_processes, handle_processes)
    tool_registry.register(tool_services, handle_services)
    tool_registry.register(tool_env, handle_env)
    tool_registry.register(tool_network, handle_network)
    tool_registry.register(tool_disk, handle_disk)
    tool_registry.register(tool_memory, handle_memory)
