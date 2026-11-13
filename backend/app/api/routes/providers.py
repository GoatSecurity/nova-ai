from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.database.repositories.provider_repo import ProviderRepository
from backend.app.providers.registry import ProviderRegistry

router = APIRouter(prefix="", tags=["Providers & Models"])

class CreateProviderRequest(BaseModel):
    name: str
    provider_type: Optional[str] = None
    base_url: str
    api_key: Optional[str] = None
    auth_type: str = "bearer"
    custom_headers: Optional[Dict[str, str]] = None
    models_endpoint: str = "/models"
    chat_endpoint: str = "/chat/completions"
    is_enabled: bool = True

def detect_provider_type(base_url: str, name: str = "") -> str:
    u = (base_url or "").lower()
    n = (name or "").lower()
    if "anthropic.com" in u or "claude" in n or "anthropic" in n:
        return "anthropic"
    if "generativelanguage.googleapis.com" in u or "gemini" in n or "google" in n:
        return "gemini"
    if ":11434" in u or "ollama" in n:
        return "ollama"
    if ":1234" in u or "lm studio" in n or "lmstudio" in n:
        return "lm_studio"
    if "groq.com" in u or "groq" in n:
        return "groq"
    if "deepseek.com" in u or "deepseek" in n:
        return "deepseek"
    return "openai_compatible" 

class UpdateProviderRequest(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    auth_type: Optional[str] = None
    custom_headers: Optional[Dict[str, str]] = None
    models_endpoint: Optional[str] = None
    chat_endpoint: Optional[str] = None
    is_enabled: Optional[bool] = None

class ManualModelRequest(BaseModel):
    model_name: str
    display_name: Optional[str] = None
    context_length: int = 8192
    supports_tools: bool = True
    supports_vision: bool = False
    is_local: bool = False

@router.get("/providers")
async def list_providers():
    return await ProviderRepository.list_providers()

@router.post("/providers")
async def create_provider(req: CreateProviderRequest):
    p_type = req.provider_type
    if not p_type or p_type == "openai_compatible":
        p_type = detect_provider_type(req.base_url, req.name)
    return await ProviderRepository.create_provider(
        name=req.name,
        provider_type=p_type,
        base_url=req.base_url,
        api_key=req.api_key,
        auth_type=req.auth_type,
        custom_headers=req.custom_headers,
        models_endpoint=req.models_endpoint,
        chat_endpoint=req.chat_endpoint,
        is_enabled=req.is_enabled
    )

@router.get("/providers/{prov_id}")
async def get_provider(prov_id: str):
    prov = await ProviderRepository.get_provider(prov_id)
    if not prov:
        raise HTTPException(status_code=404, detail="Provider not found")
    models = await ProviderRepository.list_models_for_provider(prov_id)
    return {"provider": prov, "models": models}

@router.patch("/providers/{prov_id}")
async def update_provider(prov_id: str, req: UpdateProviderRequest):
    updates = req.model_dump(exclude_unset=True)
    prov = await ProviderRepository.update_provider(prov_id, updates)
    if not prov:
        raise HTTPException(status_code=404, detail="Provider not found")
    return prov

@router.delete("/providers/{prov_id}")
async def delete_provider(prov_id: str):
    deleted = await ProviderRepository.delete_provider(prov_id)
    # Return 200 even if already deleted for idempotent deletion (prevents double-delete 404s)
    return {"status": "deleted", "id": prov_id, "existed": deleted}

class UpdateModelRequest(BaseModel):
    display_name: Optional[str] = None
    context_length: Optional[int] = None
    supports_tools: Optional[bool] = None
    supports_vision: Optional[bool] = None
    is_enabled: Optional[bool] = None

@router.patch("/models/{model_id:path}")
async def update_model(model_id: str, req: UpdateModelRequest):
    updates = req.model_dump(exclude_unset=True)
    if not updates:
        return {"status": "no_change", "id": model_id}
    from backend.app.database.connection import get_db
    async with get_db() as db:
        fields = []
        vals = []
        for k, v in updates.items():
            if isinstance(v, bool):
                v = 1 if v else 0
            fields.append(f"{k} = ?")
            vals.append(v)
        vals.append(model_id)
        vals.append(model_id)
        await db.execute(f"UPDATE provider_models SET {', '.join(fields)} WHERE id = ? OR model_name = ?;", tuple(vals))
        await db.commit()
    return {"status": "updated", "id": model_id, "updates": updates}

@router.delete("/models/{model_id:path}")
async def delete_model(model_id: str):
    deleted = await ProviderRepository.delete_model(model_id)
    return {"status": "deleted", "id": model_id, "existed": deleted}

@router.post("/providers/{prov_id}/test")
async def test_provider(prov_id: str):
    adapter = await ProviderRegistry.get_adapter_for_provider(prov_id)
    if not adapter:
        raise HTTPException(status_code=404, detail="Provider not found")
    success, message, meta = await adapter.test_connection()
    return {"success": success, "message": message, "metadata": meta}

@router.post("/providers/{prov_id}/sync-models")
async def sync_provider_models(prov_id: str):
    adapter = await ProviderRegistry.get_adapter_for_provider(prov_id)
    if not adapter:
        raise HTTPException(status_code=404, detail="Provider not found")
    discovered = await adapter.discover_models()
    if discovered:
        synced = await ProviderRepository.sync_models(prov_id, discovered)
        return {"status": "success", "count": len(synced), "models": synced, "message": f"Successfully synced {len(synced)} models from {adapter.name}."}
    
    return {
        "status": "warning",
        "count": 0,
        "models": [],
        "message": f"Could not discover any models from {adapter.base_url}. Please ensure your model server is running."
    }

@router.post("/providers/sync-all")
async def sync_all_providers():
    import asyncio
    providers = await ProviderRepository.list_providers()

    async def _sync_single(prov):
        p_id = prov["id"] if isinstance(prov, dict) else prov.id
        p_name = prov["name"] if isinstance(prov, dict) else prov.name
        adapter = await ProviderRegistry.get_adapter_for_provider(p_id)
        if not adapter:
            return {"provider_id": p_id, "name": p_name, "status": "error", "count": 0, "message": "Adapter not found"}
        try:
            discovered = await asyncio.wait_for(adapter.discover_models(), timeout=7.0)
            if discovered:
                synced = await ProviderRepository.sync_models(p_id, discovered)
                return {"provider_id": p_id, "name": p_name, "status": "success", "count": len(synced), "models": synced}
            else:
                return {"provider_id": p_id, "name": p_name, "status": "no_models", "count": 0, "models": []}
        except asyncio.TimeoutError:
            return {"provider_id": p_id, "name": p_name, "status": "timeout", "count": 0, "message": "Discovery timed out"}
        except Exception as e:
            return {"provider_id": p_id, "name": p_name, "status": "error", "count": 0, "message": str(e)}

    results = await asyncio.gather(*[_sync_single(p) for p in providers])
    total_models = sum(r.get("count", 0) for r in results)
    synced_providers = sum(1 for r in results if r.get("status") == "success")

    return {
        "status": "success",
        "total_providers": len(providers),
        "synced_providers": synced_providers,
        "total_models": total_models,
        "results": results,
        "message": f"Synced {total_models} models across {synced_providers} online providers."
    }

@router.post("/providers/{prov_id}/models")
async def add_manual_model(prov_id: str, req: ManualModelRequest):
    prov = await ProviderRepository.get_provider(prov_id)
    if not prov:
        raise HTTPException(status_code=404, detail="Provider not found")
    from backend.app.providers.openai_compatible import clean_model_display_name
    model_data = req.model_dump()
    if not model_data.get("display_name"):
        model_data["display_name"] = clean_model_display_name(model_data["model_name"])
    synced = await ProviderRepository.sync_models(prov_id, [model_data])
    return {"status": "success", "models": synced}

@router.get("/models")
async def list_all_models():
    models = await ProviderRepository.list_all_models()
    from backend.app.providers.openai_compatible import clean_model_display_name
    for m in models:
        m["display_name"] = clean_model_display_name(m.get("display_name") or m.get("model_name"))
    return models
