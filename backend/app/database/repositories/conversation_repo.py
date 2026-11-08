import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from backend.app.database.connection import get_db

class ConversationRepository:
    @staticmethod
    async def create_conversation(
        title: str,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        agent_profile_id: Optional[str] = None,
        system_prompt_id: Optional[str] = None,
        workspace_path: Optional[str] = None,
        permission_mode: str = "allow_safe"
    ) -> Dict[str, Any]:
        conv_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            await db.execute(
                """INSERT INTO conversations (
                    id, title, provider_id, model_id, agent_profile_id,
                    system_prompt_id, workspace_path, permission_mode,
                    is_pinned, is_archived, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?);""",
                (conv_id, title, provider_id, model_id, agent_profile_id,
                 system_prompt_id, workspace_path, permission_mode, now, now)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM conversations WHERE id = ?;", (conv_id,))
            row = await cursor.fetchone()
            return dict(row)

    @staticmethod
    async def list_conversations(include_archived: bool = False) -> List[Dict[str, Any]]:
        async with get_db() as db:
            query = "SELECT * FROM conversations "
            if not include_archived:
                query += "WHERE is_archived = 0 "
            query += "ORDER BY is_pinned DESC, updated_at DESC;"
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def get_conversation(conv_id: str) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM conversations WHERE id = ?;", (conv_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def update_conversation(conv_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed_fields = [
            "title", "provider_id", "model_id", "agent_profile_id",
            "system_prompt_id", "workspace_path", "permission_mode",
            "is_pinned", "is_archived"
        ]
        set_clauses = []
        values = []
        for k, v in updates.items():
            if k in allowed_fields:
                set_clauses.append(f"{k} = ?")
                values.append(v)
        if not set_clauses:
            return await ConversationRepository.get_conversation(conv_id)

        now = datetime.utcnow().isoformat() + "Z"
        set_clauses.append("updated_at = ?")
        values.append(now)
        values.append(conv_id)

        async with get_db() as db:
            await db.execute(f"UPDATE conversations SET {', '.join(set_clauses)} WHERE id = ?;", tuple(values))
            await db.commit()
            return await ConversationRepository.get_conversation(conv_id)

    @staticmethod
    async def delete_conversation(conv_id: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute("DELETE FROM conversations WHERE id = ?;", (conv_id,))
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def add_message(
        conversation_id: str,
        role: str,
        content: str,
        thoughts: Optional[str] = None,
        tokens: int = 0
    ) -> Dict[str, Any]:
        msg_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            await db.execute(
                "INSERT INTO messages (id, conversation_id, role, content, thoughts, tokens, created_at) VALUES (?, ?, ?, ?, ?, ?, ?);",
                (msg_id, conversation_id, role, content, thoughts, tokens, now)
            )
            # update conversation updated_at
            await db.execute("UPDATE conversations SET updated_at = ? WHERE id = ?;", (now, conversation_id))
            await db.commit()
            cursor = await db.execute("SELECT * FROM messages WHERE id = ?;", (msg_id,))
            row = await cursor.fetchone()
            return dict(row)

    @staticmethod
    async def get_messages(conversation_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?;",
                (conversation_id, limit)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def update_message(
        message_id: str,
        content: str,
        thoughts: Optional[str] = None,
        tokens: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            if thoughts is not None and tokens is not None:
                await db.execute(
                    "UPDATE messages SET content = ?, thoughts = ?, tokens = ? WHERE id = ?;",
                    (content, thoughts, tokens, message_id)
                )
            elif thoughts is not None:
                await db.execute(
                    "UPDATE messages SET content = ?, thoughts = ? WHERE id = ?;",
                    (content, thoughts, message_id)
                )
            else:
                await db.execute(
                    "UPDATE messages SET content = ? WHERE id = ?;",
                    (content, message_id)
                )
            await db.commit()
            cursor = await db.execute("SELECT * FROM messages WHERE id = ?;", (message_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def delete_messages_after(conversation_id: str, message_id: str) -> int:
        async with get_db() as db:
            cursor = await db.execute("SELECT created_at FROM messages WHERE id = ?;", (message_id,))
            target = await cursor.fetchone()
            if not target:
                return 0
            created_at = target["created_at"]
            del_cursor = await db.execute(
                "DELETE FROM messages WHERE conversation_id = ? AND created_at > ?;",
                (conversation_id, created_at)
            )
            await db.commit()
            return del_cursor.rowcount

    @staticmethod
    async def get_last_user_message(conversation_id: str) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM messages WHERE conversation_id = ? AND role = 'user' ORDER BY created_at DESC LIMIT 1;",
                (conversation_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
