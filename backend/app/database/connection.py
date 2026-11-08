import os
import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from backend.app.core.config import settings
from backend.app.core.logging import logger

DB_PATH = settings.DATABASE_PATH

@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Provides an async SQLite connection with WAL mode and foreign keys enabled.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    try:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA busy_timeout = 5000;")
        yield db
    finally:
        await db.close()

async def execute_query(query: str, params: tuple = ()) -> list:
    async with get_db() as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def execute_commit(query: str, params: tuple = ()) -> int:
    async with get_db() as db:
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.lastrowid or cursor.rowcount
