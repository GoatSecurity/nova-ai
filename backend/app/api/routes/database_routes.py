import os
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse
from backend.app.core.config import settings
from backend.app.database.connection import get_db

router = APIRouter(prefix="/database", tags=["Database & Storage"])

@router.get("/status")
async def get_db_status():
    db_file = settings.DATABASE_PATH
    size_bytes = db_file.stat().st_size if db_file.exists() else 0
    wal_file = Path(f"{db_file}-wal")
    wal_size = wal_file.stat().st_size if wal_file.exists() else 0

    async with get_db() as db:
        c1 = await db.execute("SELECT COUNT(*) FROM conversations;")
        (conv_count,) = await c1.fetchone()
        c2 = await db.execute("SELECT COUNT(*) FROM messages;")
        (msg_count,) = await c2.fetchone()
        c3 = await db.execute("SELECT COUNT(*) FROM tool_calls;")
        (tc_count,) = await c3.fetchone()
        c4 = await db.execute("SELECT COUNT(*) FROM memory_facts;")
        (facts_count,) = await c4.fetchone()

    return {
        "database_path": str(db_file),
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "wal_size_bytes": wal_size,
        "conversations_count": conv_count,
        "messages_count": msg_count,
        "tool_calls_count": tc_count,
        "memory_facts_count": facts_count
    }

@router.post("/vacuum")
async def vacuum_database():
    async with get_db() as db:
        await db.execute("VACUUM;")
        await db.commit()
    return {"status": "success", "message": "Database vacuumed successfully."}

@router.get("/backup")
async def download_backup():
    db_file = settings.DATABASE_PATH
    if not db_file.exists():
        return {"error": "Database file not found."}
    return FileResponse(
        path=str(db_file),
        filename=f"nova_backup_{int(os.path.getmtime(db_file))}.db",
        media_type="application/x-sqlite3"
    )
