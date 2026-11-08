import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from backend.app.database.connection import get_db

class ExecutionRepository:
    # --- Tool Calls & Results ---
    @staticmethod
    async def create_tool_call(
        message_id: str,
        conversation_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        risk_level: str = "LOW",
        status: str = "pending",
        tool_call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        call_id = tool_call_id or str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        args_json = json.dumps(arguments)
        async with get_db() as db:
            await db.execute(
                """INSERT INTO tool_calls (
                    id, message_id, conversation_id, tool_name,
                    arguments_json, risk_level, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
                (call_id, message_id, conversation_id, tool_name, args_json, risk_level, status, now)
            )
            await db.commit()
            return await ExecutionRepository.get_tool_call(call_id)

    @staticmethod
    async def get_tool_call(call_id: str) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("""
                SELECT tc.*, tr.stdout, tr.stderr, tr.exit_code, tr.duration_ms, tr.is_error, tr.output_json
                FROM tool_calls tc
                LEFT JOIN tool_results tr ON tc.id = tr.tool_call_id
                WHERE tc.id = ?;
            """, (call_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            item["arguments"] = json.loads(item.get("arguments_json") or "{}")
            if item.get("output_json"):
                item["output"] = json.loads(item["output_json"])
            return item

    @staticmethod
    async def update_tool_call_status(call_id: str, status: str):
        async with get_db() as db:
            await db.execute("UPDATE tool_calls SET status = ? WHERE id = ?;", (status, call_id))
            await db.commit()

    @staticmethod
    async def record_tool_result(
        tool_call_id: str,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        duration_ms: int = 0,
        is_error: bool = False,
        output_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        result_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        out_json = json.dumps(output_data) if output_data is not None else None
        
        async with get_db() as db:
            await db.execute(
                """INSERT OR REPLACE INTO tool_results (
                    id, tool_call_id, stdout, stderr, exit_code,
                    duration_ms, is_error, output_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (result_id, tool_call_id, stdout, stderr, exit_code, duration_ms, 1 if is_error else 0, out_json, now)
            )
            status = "failed" if is_error else "completed"
            await db.execute("UPDATE tool_calls SET status = ? WHERE id = ?;", (status, tool_call_id))
            await db.commit()
            return await ExecutionRepository.get_tool_call(tool_call_id)

    @staticmethod
    async def list_conversation_tool_calls(conversation_id: str) -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("""
                SELECT tc.*, tr.stdout, tr.stderr, tr.exit_code, tr.duration_ms, tr.is_error, tr.output_json
                FROM tool_calls tc
                LEFT JOIN tool_results tr ON tc.id = tr.tool_call_id
                WHERE tc.conversation_id = ?
                ORDER BY tc.created_at ASC;
            """, (conversation_id,))
            rows = await cursor.fetchall()
            res = []
            for r in rows:
                item = dict(r)
                item["arguments"] = json.loads(item.get("arguments_json") or "{}")
                if item.get("output_json"):
                    item["output"] = json.loads(item["output_json"])
                res.append(item)
            return res

    # --- Execution Approvals ---
    @staticmethod
    async def create_approval_request(
        conversation_id: str,
        tool_call_id: str,
        command_hash: str,
        command: str,
        shell: str,
        cwd: str,
        risk_level: str
    ) -> Dict[str, Any]:
        app_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            await db.execute(
                """INSERT INTO execution_approvals (
                    id, conversation_id, tool_call_id, command_hash,
                    command, shell, cwd, risk_level, status, decided_by,
                    created_at, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, ?, NULL);""",
                (app_id, conversation_id, tool_call_id, command_hash,
                 command, shell, cwd, risk_level, now)
            )
            await db.execute("UPDATE tool_calls SET status = 'waiting_approval' WHERE id = ?;", (tool_call_id,))
            await db.commit()
            cursor = await db.execute("SELECT * FROM execution_approvals WHERE id = ?;", (app_id,))
            row = await cursor.fetchone()
            return dict(row)

    @staticmethod
    async def list_pending_approvals(conversation_id: str) -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM execution_approvals WHERE conversation_id = ? AND status = 'pending' ORDER BY created_at ASC;",
                (conversation_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def get_approval(approval_id: str) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM execution_approvals WHERE id = ?;", (approval_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    async def decide_approval(approval_id: str, decision: str, actor: str = "user") -> Optional[Dict[str, Any]]:
        # decision: 'approved_once', 'approved_session', 'denied'
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            await db.execute(
                """UPDATE execution_approvals
                   SET status = ?, decided_by = ?, decided_at = ?
                   WHERE id = ?;""",
                (decision, actor, now, approval_id)
            )
            cursor = await db.execute("SELECT * FROM execution_approvals WHERE id = ?;", (approval_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            app_data = dict(row)
            
            # update tool_call status
            tc_status = "approved" if decision in ("approved_once", "approved_session") else "rejected"
            await db.execute("UPDATE tool_calls SET status = ? WHERE id = ?;", (tc_status, app_data["tool_call_id"]))
            await db.commit()
            return app_data

    # --- Session Permissions ---
    @staticmethod
    async def create_session_permission(
        conversation_id: str,
        scope: str,
        tool_name: Optional[str] = None,
        cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        perm_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            await db.execute(
                """INSERT INTO session_permissions (
                    id, conversation_id, scope, tool_name, cwd, created_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, 1);""",
                (perm_id, conversation_id, scope, tool_name, cwd, now)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM session_permissions WHERE id = ?;", (perm_id,))
            row = await cursor.fetchone()
            return dict(row)

    @staticmethod
    async def check_session_permission(conversation_id: str, tool_name: str, cwd: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute("""
                SELECT * FROM session_permissions
                WHERE conversation_id = ? AND is_active = 1
                AND (scope = 'all_safe' OR tool_name = ? OR tool_name = '*');
            """, (conversation_id, tool_name))
            rows = await cursor.fetchall()
            return len(rows) > 0

    @staticmethod
    async def revoke_session_permissions(conversation_id: str):
        async with get_db() as db:
            await db.execute("UPDATE session_permissions SET is_active = 0 WHERE conversation_id = ?;", (conversation_id,))
            await db.commit()
