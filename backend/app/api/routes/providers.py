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
    
    # Fallback default model placeholder when server is offline or doesn't support models endpoint
    safe_name = adapter.name.lower().replace(" ", "-")
    fallback = [{
        "model_name": safe_name,
        "display_name": f"{adapter.name} (Default)",
        "context_length": 8192,
        "supports_tools": True,
        "supports_vision": False,
        "is_local": adapter.is_local_url()
    }]
    synced = await ProviderRepository.sync_models(prov_id, fallback)
    return {
        "status": "warning",
        "count": 0,
        "models": synced,
        "message": f"Could not connect to {adapter.base_url} to discover models. Created default placeholder '{safe_name}'. Please ensure your model server is running."
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
