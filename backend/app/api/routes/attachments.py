import os
import uuid
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.app.core.config import settings
from backend.app.database.connection import get_db

router = APIRouter(prefix="/attachments", tags=["Attachments"])

ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".toml", ".log", ".csv", ".html", ".css", ".sql", ".pdf",
    ".png", ".jpg", ".jpeg", ".gif", ".webp"
}

class UploadAttachmentJSON(BaseModel):
    filename: str
    content_base64: str
    conversation_id: str
    mime_type: Optional[str] = "application/octet-stream"

@router.post("")
async def upload_attachment(req: UploadAttachmentJSON):
    ext = Path(req.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File extension '{ext}' is not permitted.")

    try:
        content = base64.b64decode(req.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content payload.")

    if len(content) > 25 * 1024 * 1024:  # 25 MB limit
        raise HTTPException(status_code=400, detail="File exceeds 25 MB upload limit.")

    att_id = str(uuid.uuid4())
    save_filename = f"{att_id}_{req.filename}"
    save_path = settings.ATTACHMENTS_DIR / save_filename
    save_path.write_bytes(content)

    now = datetime.utcnow().isoformat() + "Z"
    async with get_db() as db:
        await db.execute(
            """INSERT INTO attachments (id, conversation_id, message_id, filename, file_path, file_size, mime_type, created_at)
               VALUES (?, ?, NULL, ?, ?, ?, ?, ?);""",
            (att_id, req.conversation_id, req.filename, str(save_path), len(content), req.mime_type, now)
        )
        await db.commit()

    return {
        "id": att_id,
        "filename": req.filename,
        "file_size": len(content),
        "mime_type": req.mime_type,
        "path": str(save_path)
    }

@router.get("/{att_id}/download")
async def download_attachment(att_id: str):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM attachments WHERE id = ?;", (att_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Attachment not found")
        item = dict(row)

    target = Path(item["file_path"])
    if not target.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")

    return FileResponse(path=str(target), filename=item["filename"], media_type=item["mime_type"])
