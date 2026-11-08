import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from backend.app.database.connection import get_db

class PromptRepository:
    # --- Agent Profiles ---
    @staticmethod
    async def list_agent_profiles() -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM agent_profiles ORDER BY is_builtin DESC, name ASC;")
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                item["preferred_tools"] = json.loads(item.get("preferred_tools_json") or "[]")
                result.append(item)
            return result

    @staticmethod
    async def get_agent_profile(profile_id: str) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM agent_profiles WHERE id = ?;", (profile_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            item["preferred_tools"] = json.loads(item.get("preferred_tools_json") or "[]")
            return item

    @staticmethod
    async def create_agent_profile(
        name: str,
        description: str,
        system_instructions: str,
        preferred_tools: Optional[List[str]] = None,
        default_risk_mode: str = "allow_safe"
    ) -> Dict[str, Any]:
        profile_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            await db.execute(
                """INSERT INTO agent_profiles (
                    id, name, description, system_instructions,
                    preferred_tools_json, default_risk_mode, is_builtin, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?);""",
                (profile_id, name, description, system_instructions,
                 json.dumps(preferred_tools or []), default_risk_mode, now)
            )
            await db.commit()
            return await PromptRepository.get_agent_profile(profile_id)

    @staticmethod
    async def update_agent_profile(profile_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = await PromptRepository.get_agent_profile(profile_id)
        if not existing:
            return None

        allowed = ["name", "description", "system_instructions", "default_risk_mode"]
        set_clauses = []
        values = []
        for k in allowed:
            if k in updates:
                set_clauses.append(f"{k} = ?")
                values.append(updates[k])

        if "preferred_tools" in updates:
            set_clauses.append("preferred_tools_json = ?")
            values.append(json.dumps(updates["preferred_tools"]))

        if set_clauses:
            values.append(profile_id)
            async with get_db() as db:
                await db.execute(f"UPDATE agent_profiles SET {', '.join(set_clauses)} WHERE id = ?;", tuple(values))
                await db.commit()
        return await PromptRepository.get_agent_profile(profile_id)

    @staticmethod
    async def delete_agent_profile(profile_id: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute("DELETE FROM agent_profiles WHERE id = ? AND is_builtin = 0;", (profile_id,))
            await db.commit()
            return cursor.rowcount > 0

    # --- System Prompts ---
    @staticmethod
    async def list_system_prompts() -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM system_prompts ORDER BY is_global DESC, is_active DESC, name ASC;")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def get_system_prompt(prompt_id: str) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM system_prompts WHERE id = ?;", (prompt_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def get_active_global_prompt() -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM system_prompts WHERE is_global = 1 AND is_active = 1 LIMIT 1;")
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def create_system_prompt(name: str, content: str, is_global: bool = False) -> Dict[str, Any]:
        prompt_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            if is_global:
                await db.execute("UPDATE system_prompts SET is_global = 0 WHERE is_global = 1;")
            await db.execute(
                "INSERT INTO system_prompts (id, name, content, is_global, is_active, created_at) VALUES (?, ?, ?, ?, 1, ?);",
                (prompt_id, name, content, 1 if is_global else 0, now)
            )
            await db.commit()
            return await PromptRepository.get_system_prompt(prompt_id)

    @staticmethod
    async def update_system_prompt(prompt_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = ["name", "content", "is_global", "is_active"]
        set_clauses = []
        values = []
        for k in allowed:
            if k in updates:
                set_clauses.append(f"{k} = ?")
                values.append(updates[k])

        if not set_clauses:
            return await PromptRepository.get_system_prompt(prompt_id)

        values.append(prompt_id)
        async with get_db() as db:
            if updates.get("is_global"):
                await db.execute("UPDATE system_prompts SET is_global = 0 WHERE id != ?;", (prompt_id,))
            await db.execute(f"UPDATE system_prompts SET {', '.join(set_clauses)} WHERE id = ?;", tuple(values))
            await db.commit()
            return await PromptRepository.get_system_prompt(prompt_id)

    @staticmethod
    async def delete_system_prompt(prompt_id: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute("DELETE FROM system_prompts WHERE id = ?;", (prompt_id,))
            await db.commit()
            return cursor.rowcount > 0

    # --- Project Workspaces ---
    @staticmethod
    async def list_workspaces() -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM project_workspaces ORDER BY is_active DESC, name ASC;")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def set_active_workspace(ws_id: str) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            await db.execute("UPDATE project_workspaces SET is_active = 0;")
            await db.execute("UPDATE project_workspaces SET is_active = 1 WHERE id = ?;", (ws_id,))
            await db.commit()
            cursor = await db.execute("SELECT * FROM project_workspaces WHERE id = ?;", (ws_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
