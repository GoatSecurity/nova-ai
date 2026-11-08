import uuid
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from backend.app.database.connection import get_db
from backend.app.core.security import encrypt_credential, decrypt_credential, mask_credential

class ProviderRepository:
    @staticmethod
    async def create_provider(
        name: str,
        provider_type: str,
        base_url: str,
        api_key: Optional[str] = None,
        auth_type: str = "bearer",
        custom_headers: Optional[Dict[str, str]] = None,
        models_endpoint: str = "/models",
        chat_endpoint: str = "/chat/completions",
        is_enabled: bool = True
    ) -> Dict[str, Any]:
        prov_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        encrypted_key = encrypt_credential(api_key) if api_key else ""
        headers_json = json.dumps(custom_headers or {})

        async with get_db() as db:
            await db.execute(
                """INSERT INTO providers (
                    id, name, provider_type, base_url, api_key_encrypted,
                    auth_type, custom_headers_json, models_endpoint,
                    chat_endpoint, is_enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (prov_id, name, provider_type, base_url, encrypted_key,
                 auth_type, headers_json, models_endpoint, chat_endpoint,
                 1 if is_enabled else 0, now, now)
            )
            await db.commit()
            return await ProviderRepository.get_provider(prov_id, include_decrypted_key=False)

    @staticmethod
    async def list_providers(include_decrypted_key: bool = False) -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM providers ORDER BY created_at ASC;")
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                raw_key = decrypt_credential(item["api_key_encrypted"]) if item["api_key_encrypted"] else ""
                item["api_key_masked"] = mask_credential(raw_key)
                if include_decrypted_key:
                    item["api_key_decrypted"] = raw_key
                del item["api_key_encrypted"]
                item["custom_headers"] = json.loads(item.get("custom_headers_json") or "{}")
                result.append(item)
            return result

    @staticmethod
    async def get_provider(prov_id: str, include_decrypted_key: bool = False) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM providers WHERE id = ?;", (prov_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            raw_key = decrypt_credential(item["api_key_encrypted"]) if item["api_key_encrypted"] else ""
            item["api_key_masked"] = mask_credential(raw_key)
            if include_decrypted_key:
                item["api_key_decrypted"] = raw_key
            del item["api_key_encrypted"]
            item["custom_headers"] = json.loads(item.get("custom_headers_json") or "{}")
            return item

    @staticmethod
    async def update_provider(prov_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = await ProviderRepository.get_provider(prov_id, include_decrypted_key=True)
        if not existing:
            return None

        allowed = [
            "name", "provider_type", "base_url", "auth_type",
            "models_endpoint", "chat_endpoint", "is_enabled"
        ]
        set_clauses = []
        values = []
        for k in allowed:
            if k in updates:
                set_clauses.append(f"{k} = ?")
                values.append(updates[k])

        if "api_key" in updates and updates["api_key"] is not None:
            set_clauses.append("api_key_encrypted = ?")
            values.append(encrypt_credential(updates["api_key"]))

        if "custom_headers" in updates:
            set_clauses.append("custom_headers_json = ?")
            values.append(json.dumps(updates["custom_headers"]))

        if not set_clauses:
            return existing

        now = datetime.utcnow().isoformat() + "Z"
        set_clauses.append("updated_at = ?")
        values.append(now)
        values.append(prov_id)

        async with get_db() as db:
            await db.execute(f"UPDATE providers SET {', '.join(set_clauses)} WHERE id = ?;", tuple(values))
            await db.commit()
            return await ProviderRepository.get_provider(prov_id)

    @staticmethod
    async def delete_provider(prov_id: str) -> bool:
        async with get_db() as db:
            # Cascading deletion of all models associated with this provider
            await db.execute("DELETE FROM provider_models WHERE provider_id = ?;", (prov_id,))
            cursor = await db.execute("DELETE FROM providers WHERE id = ?;", (prov_id,))
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def delete_model(model_id: str) -> bool:
        async with get_db() as db:
            cursor = await db.execute("DELETE FROM provider_models WHERE id = ?;", (model_id,))
            await db.commit()
            return cursor.rowcount > 0

    @staticmethod
    async def sync_models(provider_id: str, models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Replaces or upserts discovered models for a provider.
        """
        now = datetime.utcnow().isoformat() + "Z"
        async with get_db() as db:
            for m in models:
                model_name = m["model_name"]
                model_id = f"{provider_id}:{model_name}"
                display_name = m.get("display_name") or model_name
                context_length = m.get("context_length", 8192)
                supports_tools = 1 if m.get("supports_tools", True) else 0
                supports_vision = 1 if m.get("supports_vision", False) else 0
                is_local = 1 if m.get("is_local", False) else 0

                await db.execute(
                    """INSERT INTO provider_models (
                        id, provider_id, model_name, display_name,
                        context_length, supports_tools, supports_vision,
                        is_local, is_enabled, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        display_name = excluded.display_name,
                        context_length = excluded.context_length,
                        supports_tools = excluded.supports_tools,
                        supports_vision = excluded.supports_vision,
                        is_local = excluded.is_local;""",
                    (model_id, provider_id, model_name, display_name,
                     context_length, supports_tools, supports_vision, is_local, now)
                )
            await db.commit()
            return await ProviderRepository.list_models_for_provider(provider_id)

    @staticmethod
    async def list_models_for_provider(provider_id: str) -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM provider_models WHERE provider_id = ? AND is_enabled = 1 ORDER BY created_at ASC, rowid ASC;",
                (provider_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def list_all_models() -> List[Dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute("""
                SELECT m.*, p.name as provider_name, p.provider_type, p.is_enabled as provider_enabled
                FROM provider_models m
                JOIN providers p ON m.provider_id = p.id
                WHERE m.is_enabled = 1 AND p.is_enabled = 1
                ORDER BY p.created_at ASC, p.rowid ASC, m.created_at ASC, m.rowid ASC;
            """)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
