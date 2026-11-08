import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from backend.app.database.connection import get_db

class MCPRepository:
    @staticmethod
    async def list_servers() -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM mcp_servers ORDER BY created_at ASC;")
            rows = await cursor.fetchall()
            res = []
            for r in rows:
                item = dict(r)
                item["args"] = json.loads(item.get("args_json") or "[]")
                item["env"] = json.loads(item.get("env_json") or "{}")
                item["tools"] = json.loads(item.get("tools_json") or "[]")
                res.append(item)
            return res

    @staticmethod
    async def get_server(server_id: str) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM mcp_servers WHERE id = ?;", (server_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            item["args"] = json.loads(item.get("args_json") or "[]")
            item["env"] = json.loads(item.get("env_json") or "{}")
            item["tools"] = json.loads(item.get("tools_json") or "[]")
            return item

    @staticmethod
    async def create_server(
        name: str,
        transport_type: str = "stdio",
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        url: Optional[str] = None,
        is_enabled: int = 1
    ) -> Dict[str, Any]:
        server_id = "mcp-" + str(uuid.uuid4())[:8]
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            await db.execute(
                """INSERT INTO mcp_servers (
                    id, name, transport_type, command, args_json, env_json,
                    url, is_enabled, status, last_error, tools_count, tools_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'disconnected', '', 0, '[]', ?, ?);""",
                (
                    server_id,
                    name.strip(),
                    transport_type.strip(),
                    command.strip() if command else "",
                    json.dumps(args or []),
                    json.dumps(env or {}),
                    url.strip() if url else "",
                    is_enabled,
                    now,
                    now
                )
            )
            await db.commit()
        return await MCPRepository.get_server(server_id)

    @staticmethod
    async def update_server(server_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed = ["name", "transport_type", "command", "url", "is_enabled", "status", "last_error", "tools_count", "tools_json"]
        updates = []
        params = []
        for k in allowed:
            if k in data:
                updates.append(f"{k} = ?")
                params.append(data[k])
        if "args" in data:
            updates.append("args_json = ?")
            params.append(json.dumps(data["args"]))
        if "env" in data:
            updates.append("env_json = ?")
            params.append(json.dumps(data["env"]))

        now = datetime.utcnow().isoformat() + "Z"
        updates.append("updated_at = ?")
        params.append(now)

        params.append(server_id)
        sql = f"UPDATE mcp_servers SET {', '.join(updates)} WHERE id = ?;"
        async with get_db() as db:
            await db.execute(sql, tuple(params))
            await db.commit()
        return await MCPRepository.get_server(server_id)

    @staticmethod
    async def delete_server(server_id: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute("DELETE FROM mcp_servers WHERE id = ?;", (server_id,))
            await db.commit()
            return cursor.rowcount > 0
