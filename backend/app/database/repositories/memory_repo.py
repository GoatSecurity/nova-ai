import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from backend.app.database.connection import get_db

class MemoryRepository:
    # --- Memory Facts ---
    @staticmethod
    async def save_fact(
        conversation_id: Optional[str],
        category: str,
        content: str,
        confidence: float = 1.0
    ) -> Dict[str, Any]:
        fact_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            await db.execute(
                """INSERT INTO memory_facts (id, conversation_id, category, content, confidence, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?);""",
                (fact_id, conversation_id, category, content, confidence, now, now)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM memory_facts WHERE id = ?;", (fact_id,))
            row = await cursor.fetchone()
            return dict(row)

    @staticmethod
    async def list_facts(category: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        async with get_db() as db:
            if category:
                cursor = await db.execute("SELECT * FROM memory_facts WHERE category = ? ORDER BY updated_at DESC LIMIT ?;", (category, limit))
            else:
                cursor = await db.execute("SELECT * FROM memory_facts ORDER BY updated_at DESC LIMIT ?;", (limit,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def search_facts(query: str, limit: int = 10) -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM memory_facts WHERE content LIKE ? ORDER BY updated_at DESC LIMIT ?;",
                (f"%{query}%", limit)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def delete_fact(fact_id: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute("DELETE FROM memory_facts WHERE id = ?;", (fact_id,))
            await db.commit()
            return cursor.rowcount > 0

    # --- Conversation Summaries ---
    @staticmethod
    async def get_summary(conversation_id: str) -> Optional[str]:
        async with get_db() as db:
            cursor = await db.execute("SELECT summary_text FROM conversation_summaries WHERE conversation_id = ?;", (conversation_id,))
            row = await cursor.fetchone()
            return row["summary_text"] if row else None

    @staticmethod
    async def save_summary(conversation_id: str, summary_text: str, last_message_id: Optional[str] = None):
        summary_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            await db.execute(
                """INSERT INTO conversation_summaries (id, conversation_id, summary_text, last_message_id, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(conversation_id) DO UPDATE SET
                       summary_text = excluded.summary_text,
                       last_message_id = excluded.last_message_id,
                       updated_at = excluded.updated_at;""",
                (summary_id, conversation_id, summary_text, last_message_id, now)
            )
            await db.commit()

    # --- FTS5 Message Full-Text Search ---
    @staticmethod
    async def search_messages_fts(query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Uses SQLite FTS5 index to search across all conversations.
        """
        async with get_db() as db:
            try:
                # Sanitize query for FTS5 syntax
                clean_q = '"' + query.replace('"', '""') + '"'
                cursor = await db.execute("""
                    SELECT m.id, m.conversation_id, m.role, m.content, m.created_at, c.title as conversation_title
                    FROM messages_fts fts
                    JOIN messages m ON fts.message_id = m.id
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE messages_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?;
                """, (clean_q, limit))
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
            except Exception:
                # Fallback to standard LIKE if FTS query syntax error
                cursor = await db.execute("""
                    SELECT m.id, m.conversation_id, m.role, m.content, m.created_at, c.title as conversation_title
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE m.content LIKE ?
                    ORDER BY m.created_at DESC
                    LIMIT ?;
                """, (f"%{query}%", limit))
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
