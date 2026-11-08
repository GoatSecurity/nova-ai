import json
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel
from backend.app.database.connection import get_db
from backend.app.core.config import settings

router = APIRouter(prefix="/settings", tags=["Settings"])

DEFAULT_APP_SETTINGS = {
    "general": {
        "appName": "NOVA",
        "language": "en-US",
        "checkUpdates": True,
        "telemetry": False
    },
    "appearance": {
        "theme": "dark",
        "accentColor": "emerald",
        "fontFamily": "Inter, system-ui, sans-serif",
        "fontSize": 14,
        "reduceMotion": False,
        "streamTypingSpeed": 20
    },
    "permissions": {
        "defaultMode": settings.DEFAULT_PERMISSION_MODE,
        "autoApproveSafe": True,
        "requireExplicitAdmin": True,
        "sessionGrantTtlMinutes": 60,
        "strictWorkspaceBoundary": True
    },
    "terminal": {
        "defaultShell": "powershell",
        "executionTimeoutSeconds": settings.DEFAULT_EXECUTION_TIMEOUT,
        "maxOutputBytes": settings.MAX_OUTPUT_BYTES,
        "powershellBypassPolicy": True,
        "enableAnsiColors": True
    },
    "memory": {
        "enablePersistentMemory": True,
        "autoSaveInsights": True,
        "maxMemoryFacts": 500,
        "enableFtsSearch": True
    },
    "context": {
        "maxContextTokens": settings.MAX_CONTEXT_TOKENS,
        "reserveResponseTokens": settings.RESERVE_TOKENS_FOR_RESPONSE,
        "autoSummarizeAtTokens": 24000
    }
}

@router.get("")
async def get_all_settings():
    async with get_db() as db:
        cursor = await db.execute("SELECT key, value_json FROM application_settings;")
        rows = await cursor.fetchall()
        result = DEFAULT_APP_SETTINGS.copy()
        for r in rows:
            try:
                result[r["key"]] = json.loads(r["value_json"])
            except Exception:
                pass
        return result

class UpdateSettingSection(BaseModel):
    values: Dict[str, Any]

@router.post("/{section_key}")
async def update_settings_section(section_key: str, req: UpdateSettingSection):
    now = datetime.utcnow().isoformat() + "Z"
    val_json = json.dumps(req.values)
    async with get_db() as db:
        await db.execute(
            """INSERT INTO application_settings (key, value_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value_json = excluded.value_json,
                   updated_at = excluded.updated_at;""",
            (section_key, val_json, now)
        )
        await db.commit()
    return {"status": "saved", "section": section_key, "values": req.values}
