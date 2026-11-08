import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.app.database.repositories.prompt_repo import PromptRepository
from backend.app.database.connection import get_db
from backend.app.core.config import settings

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])

class CreateWorkspaceRequest(BaseModel):
    name: str
    path: str
    description: Optional[str] = ""

@router.get("/file-content")
async def get_file_content(path: str = Query(...)):
    raw_path = path.strip('\'" \t\r\n')
    clean_path_str = raw_path.replace("\\", "/")
    target = Path(clean_path_str)

    # 1. Check if directly exists as resolved path
    try:
        is_direct = target.exists() and target.is_file()
    except Exception:
        is_direct = False

    if not is_direct:
        # 2. Check relative to active workspace, default workspace and scratch
        candidates = [
            Path(settings.DEFAULT_WORKSPACE) / clean_path_str,
            settings.SCRATCH_DIR / clean_path_str,
            settings.BASE_DIR / clean_path_str,
            Path.cwd() / clean_path_str,
        ]
        
        try:
            active_ws = await PromptRepository.get_active_workspace()
            if active_ws and active_ws.get("path"):
                candidates.insert(0, Path(active_ws["path"]) / clean_path_str)
        except Exception:
            pass

        found = False
        for c in candidates:
            try:
                if c.exists() and c.is_file():
                    target = c.resolve()
                    found = True
                    break
            except Exception:
                continue
        
        # 3. Robust fallback: extract basename and search in scratch workspace
        if not found:
            # Extract candidate filename or extension suffix
            match_ext = re.search(r'([a-zA-Z0-9_-]+\.[a-zA-Z0-9]+)$', raw_path)
            candidate_name = match_ext.group(1) if match_ext else re.split(r'[/\\:\r\n ]', raw_path)[-1].strip()
            if candidate_name:
                for base in [Path(settings.DEFAULT_WORKSPACE), settings.SCRATCH_DIR, settings.BASE_DIR]:
                    if base.exists():
                        for root, _, files in os.walk(str(base)):
                            for f in files:
                                if f.lower() == candidate_name.lower() or f.lower().endswith(candidate_name.lower()):
                                    target = Path(root) / f
                                    found = True
                                    break
                            if found:
                                break
                    if found:
                        break

        if not found:
            try:
                if not (target.exists() and target.is_file()):
                    raise HTTPException(status_code=404, detail=f"File not found: {raw_path}")
            except Exception:
                raise HTTPException(status_code=404, detail=f"File not found: {raw_path}")

    target = target.resolve()
    if target.is_dir():
        raise HTTPException(status_code=400, detail="Target path is a directory, not a file")

    try:
        size = target.stat().st_size
        if size > 2 * 1024 * 1024:
            content = target.read_text(encoding="utf-8", errors="replace")[:100000] + "\n\n... [File content truncated: file exceeds 2MB] ..."
        else:
            for enc in ("utf-8", "cp1252", "latin-1"):
                try:
                    content = target.read_text(encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                content = target.read_text(encoding="utf-8", errors="replace")
        return {
            "path": str(target),
            "filename": target.name,
            "size": size,
            "content": content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

@router.get("")
async def list_workspaces():
    return await PromptRepository.list_workspaces()

@router.post("")
async def create_workspace(req: CreateWorkspaceRequest):
    p = Path(req.path).resolve()
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"Directory path '{req.path}' does not exist on disk.")
    import uuid
    from datetime import datetime
    ws_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    async with get_db() as db:
        await db.execute(
            "INSERT INTO project_workspaces (id, name, path, description, is_active, created_at) VALUES (?, ?, ?, ?, 0, ?);",
            (ws_id, req.name, str(p), req.description or "", now)
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM project_workspaces WHERE id = ?;", (ws_id,))
        row = await cursor.fetchone()
        return dict(row)

@router.post("/{ws_id}/activate")
async def activate_workspace(ws_id: str):
    ws = await PromptRepository.set_active_workspace(ws_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws
