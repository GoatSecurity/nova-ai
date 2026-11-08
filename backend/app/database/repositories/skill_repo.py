import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from backend.app.database.connection import get_db

class SkillRepository:
    @staticmethod
    async def list_skills() -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM skills ORDER BY is_builtin DESC, name ASC;")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def get_skill(skill_id: str) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM skills WHERE id = ?;", (skill_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def get_skill_by_command(command: str) -> Optional[Dict[str, Any]]:
        clean_cmd = command.strip().lower()
        if not clean_cmd.startswith("/"):
            clean_cmd = "/" + clean_cmd
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM skills WHERE LOWER(command) = ?;", (clean_cmd,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def create_skill(
        name: str,
        command: str,
        description: str,
        system_prompt: str,
        icon: str = "sparkles",
        color: str = "indigo"
    ) -> Dict[str, Any]:
        skill_id = "skill-" + str(uuid.uuid4())[:8]
        clean_cmd = command.strip().lower()
        if not clean_cmd.startswith("/"):
            clean_cmd = "/" + clean_cmd
            
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            await db.execute(
                """INSERT INTO skills (
                    id, name, command, description, system_prompt, icon, color, is_builtin, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?);""",
                (skill_id, name.strip(), clean_cmd, description.strip(), system_prompt.strip(), icon, color, now)
            )
            await db.commit()
        return await SkillRepository.get_skill(skill_id)

    @staticmethod
    async def update_skill(skill_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = ["name", "command", "description", "system_prompt", "icon", "color"]
        updates = []
        params = []
        for k in allowed:
            if k in data:
                val = data[k]
                if k == "command":
                    val = val.strip().lower()
                    if not val.startswith("/"):
                        val = "/" + val
                updates.append(f"{k} = ?")
                params.append(val)
        if not updates:
            return await SkillRepository.get_skill(skill_id)
        params.append(skill_id)
        sql = f"UPDATE skills SET {', '.join(updates)} WHERE id = ?;"
        async with get_db() as db:
            await db.execute(sql, tuple(params))
            await db.commit()
        return await SkillRepository.get_skill(skill_id)

    @staticmethod
    async def delete_skill(skill_id: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute("DELETE FROM skills WHERE id = ? AND is_builtin = 0;", (skill_id,))
            await db.commit()
            return cursor.rowcount > 0
