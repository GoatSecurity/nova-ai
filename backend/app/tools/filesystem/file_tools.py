import os
import shutil
import difflib
from pathlib import Path
from typing import Dict, Any, List
from backend.app.tools.base import BaseTool, ToolParameter
from backend.app.tools.registry import tool_registry
from backend.app.core.security import validate_workspace_path, is_protected_nova_core_path
from backend.app.core.config import settings
from backend.app.execution.approval import ApprovalManager
from backend.app.core.logging import audit_log

tool_list_dir = BaseTool(
    name="list_directory",
    description="Lists files and subdirectories in a directory with file sizes and modification times.",
    category="filesystem",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="path", type="string", description="Directory path to inspect (defaults to current workspace)", required=False)
    ]
)

tool_search_files = BaseTool(
    name="search_files",
    description="Recursively searches for files matching a glob pattern (e.g. '*.py', '*.ts').",
    category="filesystem",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="pattern", type="string", description="Glob pattern (e.g. '*.py', '**/*.json')"),
        ToolParameter(name="directory", type="string", description="Directory to search in", required=False),
        ToolParameter(name="limit", type="integer", description="Max results (default 50)", required=False, default=50)
    ]
)

tool_read_file = BaseTool(
    name="read_file",
    description="Reads and returns the contents of a text file (with line limits and byte offset support).",
    category="filesystem",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="path", type="string", description="Absolute or workspace-relative path to the file"),
        ToolParameter(name="max_lines", type="integer", description="Maximum lines to read (default 500)", required=False, default=500),
        ToolParameter(name="start_line", type="integer", description="Line number to start reading from (1-based)", required=False, default=1)
    ]
)

tool_create_file = BaseTool(
    name="create_file",
    description="Creates a new file with specified content. Creates parent directories automatically.",
    category="filesystem",
    risk_level="MODERATE",
    requires_approval=True,
    parameters=[
        ToolParameter(name="path", type="string", description="Path of the file to create"),
        ToolParameter(name="content", type="string", description="Text content to write"),
        ToolParameter(name="overwrite", type="boolean", description="Whether to overwrite if file already exists", required=False, default=False)
    ]
)

tool_edit_file = BaseTool(
    name="edit_file",
    description="Replaces a target block of text inside an existing file with new content without rewriting the whole file.",
    category="filesystem",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="path", type="string", description="Path of the file to edit"),
        ToolParameter(name="target", type="string", description="Exact text block in the file to replace"),
        ToolParameter(name="replacement", type="string", description="New replacement text content")
    ]
)

tool_move_file = BaseTool(
    name="move_file",
    description="Moves or renames a file or directory.",
    category="filesystem",
    risk_level="MODERATE",
    requires_approval=True,
    parameters=[
        ToolParameter(name="source_path", type="string", description="Path of source file or folder"),
        ToolParameter(name="destination_path", type="string", description="Path of destination")
    ]
)

tool_copy_file = BaseTool(
    name="copy_file",
    description="Copies a file or folder to a new location.",
    category="filesystem",
    risk_level="MODERATE",
    requires_approval=True,
    parameters=[
        ToolParameter(name="source_path", type="string", description="Source path"),
        ToolParameter(name="destination_path", type="string", description="Destination path")
    ]
)

tool_delete_file = BaseTool(
    name="delete_file",
    description="Deletes a file or directory. High-risk operation requiring explicit authorization.",
    category="filesystem",
    risk_level="HIGH",
    requires_approval=True,
    parameters=[
        ToolParameter(name="path", type="string", description="File or directory path to remove"),
        ToolParameter(name="recursive", type="boolean", description="Whether to recursively remove directory", required=False, default=False)
    ]
)

tool_create_directory = BaseTool(
    name="create_directory",
    description="Creates a new directory structure.",
    category="filesystem",
    risk_level="MODERATE",
    requires_approval=False,
    parameters=[
        ToolParameter(name="path", type="string", description="Directory path to create")
    ]
)

tool_file_metadata = BaseTool(
    name="inspect_file_metadata",
    description="Returns file size, created timestamp, modified timestamp, permissions, and extension.",
    category="filesystem",
    risk_level="LOW",
    requires_approval=False,
    parameters=[
        ToolParameter(name="path", type="string", description="File path to inspect")
    ]
)

# --- Handlers ---

def resolve_path(path_str: str, ctx: Dict[str, Any]) -> Path:
    ws = ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE
    target = Path(path_str)
    if not target.is_absolute():
        return (Path(ws) / target).resolve()
    return target.resolve()

async def handle_list_directory(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    raw_path = args.get("path") or ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE
    target = resolve_path(raw_path, ctx)
    if not target.exists():
        return {"error": f"Path '{target}' does not exist."}
    if not target.is_dir():
        return {"error": f"Path '{target}' is a file, not a directory."}

    items = []
    try:
        for entry in os.scandir(target):
            try:
                stat = entry.stat()
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size_bytes": stat.st_size if entry.is_file() else 0,
                    "modified": stat.st_mtime
                })
            except Exception:
                continue
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"directory": str(target), "total_items": len(items), "items": items[:200]}
    except Exception as e:
        return {"error": f"Failed to list directory: {str(e)}"}

async def handle_search_files(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    pattern = args.get("pattern", "*")
    raw_dir = args.get("directory") or ctx.get("workspace_path") or settings.DEFAULT_WORKSPACE
    target = resolve_path(raw_dir, ctx)
    limit = args.get("limit", 50)

    if not target.exists():
        return {"error": f"Directory '{target}' does not exist."}

    matches = []
    try:
        for p in target.glob(pattern):
            if p.is_file():
                matches.append({
                    "path": str(p),
                    "relative": str(p.relative_to(target)),
                    "size_bytes": p.stat().st_size
                })
                if len(matches) >= limit:
                    break
        return {"matches": matches, "count": len(matches)}
    except Exception as e:
        return {"error": f"File search error: {str(e)}"}

async def handle_read_file(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    target = resolve_path(args.get("path", ""), ctx)
    if not target.exists():
        return {"error": f"File '{target}' does not exist."}
    if target.is_dir():
        return {"error": f"'{target}' is a directory, not a file."}

    max_lines = args.get("max_lines", 500)
    start_line = max(1, args.get("start_line", 1))

    try:
        # Multi-encoding read
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                lines = target.read_text(encoding=enc).splitlines()
                break
            except UnicodeDecodeError:
                continue
        else:
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()

        total_lines = len(lines)
        selected_lines = lines[start_line - 1 : start_line - 1 + max_lines]
        content = "\n".join(selected_lines)

        return {
            "path": str(target),
            "total_lines": total_lines,
            "start_line": start_line,
            "lines_returned": len(selected_lines),
            "content": content
        }
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}

async def handle_create_file(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    target = resolve_path(args.get("path", ""), ctx)
    content = args.get("content", "")
    overwrite = args.get("overwrite", False)

    is_protected, block_reason = is_protected_nova_core_path(target)
    if is_protected:
        audit_log("CORE_SELF_MODIFICATION_BLOCKED", "system", {"tool": "create_file", "path": str(target)})
        return {"error": block_reason}

    if target.exists() and not overwrite:
        return {"error": f"File '{target}' already exists and overwrite=False."}

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        audit_log("FILE_CREATED", "agent", {"path": str(target), "bytes": len(content)})
        return {
            "status": "success",
            "path": str(target),
            "bytes_written": len(content.encode("utf-8")),
            "message": f"File created at {target}"
        }
    except Exception as e:
        return {"error": f"Failed to create file: {str(e)}"}

async def handle_edit_file(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    target = resolve_path(args.get("path", ""), ctx)
    old_target = args.get("target", "")
    replacement = args.get("replacement", "")

    is_protected, block_reason = is_protected_nova_core_path(target)
    if is_protected:
        audit_log("CORE_SELF_MODIFICATION_BLOCKED", "system", {"tool": "edit_file", "path": str(target)})
        return {"error": block_reason}

    if not target.exists():
        return {"error": f"File '{target}' does not exist."}

    try:
        raw_bytes = target.read_bytes()
        encoding_used = "utf-8"
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                original = raw_bytes.decode(enc)
                encoding_used = enc
                break
            except UnicodeDecodeError:
                continue
        else:
            original = raw_bytes.decode("utf-8", errors="replace")

        if old_target in original:
            new_content = original.replace(old_target, replacement, 1)
        else:
            norm_original = original.replace("\r\n", "\n")
            norm_target = old_target.replace("\r\n", "\n")
            if norm_target in norm_original:
                norm_replacement = replacement.replace("\r\n", "\n")
                new_norm = norm_original.replace(norm_target, norm_replacement, 1)
                new_content = new_norm.replace("\n", "\r\n") if "\r\n" in original else new_norm
            else:
                return {
                    "error": "Target string not found in file. Make sure target matches existing content including whitespace."
                }

        orig_lines = original.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(orig_lines, new_lines, fromfile=f"a/{target.name}", tofile=f"b/{target.name}"))

        target.write_bytes(new_content.encode(encoding_used))
        audit_log("FILE_EDITED", "agent", {"path": str(target), "diff": diff})

        return {
            "status": "success",
            "path": str(target),
            "diff": diff,
            "message": "File successfully updated."
        }
    except Exception as e:
        return {"error": f"Failed to edit file: {str(e)}"}

async def handle_move_file(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    src = resolve_path(args.get("source_path", ""), ctx)
    dst = resolve_path(args.get("destination_path", ""), ctx)
    for chk_path in (src, dst):
        is_protected, block_reason = is_protected_nova_core_path(chk_path)
        if is_protected:
            audit_log("CORE_SELF_MODIFICATION_BLOCKED", "system", {"tool": "move_file", "path": str(chk_path)})
            return {"error": block_reason}
    if not src.exists():
        return {"error": f"Source '{src}' does not exist."}
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        audit_log("FILE_MOVED", "agent", {"from": str(src), "to": str(dst)})
        return {"status": "success", "from": str(src), "to": str(dst)}
    except Exception as e:
        return {"error": f"Failed to move file: {str(e)}"}

async def handle_copy_file(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    src = resolve_path(args.get("source_path", ""), ctx)
    dst = resolve_path(args.get("destination_path", ""), ctx)
    is_protected, block_reason = is_protected_nova_core_path(dst)
    if is_protected:
        audit_log("CORE_SELF_MODIFICATION_BLOCKED", "system", {"tool": "copy_file", "path": str(dst)})
        return {"error": block_reason}
    if not src.exists():
        return {"error": f"Source '{src}' does not exist."}
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        else:
            shutil.copy2(str(src), str(dst))
        audit_log("FILE_COPIED", "agent", {"from": str(src), "to": str(dst)})
        return {"status": "success", "from": str(src), "to": str(dst)}
    except Exception as e:
        return {"error": f"Failed to copy file: {str(e)}"}

async def handle_delete_file(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    target = resolve_path(args.get("path", ""), ctx)
    recursive = args.get("recursive", False)

    is_protected, block_reason = is_protected_nova_core_path(target)
    if is_protected:
        audit_log("CORE_SELF_MODIFICATION_BLOCKED", "system", {"tool": "delete_file", "path": str(target)})
        return {"error": block_reason}

    if not target.exists():
        return {"error": f"Path '{target}' does not exist."}

    # Block deleting system root drives
    if str(target).rstrip("\\/").endswith(":") or len(target.parts) <= 1:
        return {"error": "CRITICAL: Attempt to delete root volume was blocked by application security."}

    try:
        if target.is_dir():
            if not recursive:
                target.rmdir()
            else:
                shutil.rmtree(str(target))
        else:
            target.unlink()

        audit_log("FILE_DELETED", "agent", {"path": str(target), "recursive": recursive})
        return {"status": "success", "deleted": str(target)}
    except Exception as e:
        return {"error": f"Failed to delete '{target}': {str(e)}"}

async def handle_create_directory(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    target = resolve_path(args.get("path", ""), ctx)
    is_protected, block_reason = is_protected_nova_core_path(target)
    if is_protected:
        audit_log("CORE_SELF_MODIFICATION_BLOCKED", "system", {"tool": "create_directory", "path": str(target)})
        return {"error": block_reason}
    try:
        target.mkdir(parents=True, exist_ok=True)
        return {"status": "success", "directory": str(target)}
    except Exception as e:
        return {"error": f"Failed to create directory: {str(e)}"}

async def handle_file_metadata(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    target = resolve_path(args.get("path", ""), ctx)
    if not target.exists():
        return {"error": f"Path '{target}' does not exist."}
    try:
        stat = target.stat()
        return {
            "path": str(target),
            "name": target.name,
            "is_dir": target.is_dir(),
            "is_file": target.is_file(),
            "size_bytes": stat.st_size if target.is_file() else 0,
            "created_timestamp": stat.st_ctime,
            "modified_timestamp": stat.st_mtime,
            "suffix": target.suffix
        }
    except Exception as e:
        return {"error": f"Failed to get metadata: {str(e)}"}

def register_filesystem_tools():
    tool_registry.register(tool_list_dir, handle_list_directory)
    tool_registry.register(tool_search_files, handle_search_files)
    tool_registry.register(tool_read_file, handle_read_file)
    tool_registry.register(tool_create_file, handle_create_file)
    tool_registry.register(tool_edit_file, handle_edit_file)
    tool_registry.register(tool_move_file, handle_move_file)
    tool_registry.register(tool_copy_file, handle_copy_file)
    tool_registry.register(tool_delete_file, handle_delete_file)
    tool_registry.register(tool_create_directory, handle_create_directory)
    tool_registry.register(tool_file_metadata, handle_file_metadata)
