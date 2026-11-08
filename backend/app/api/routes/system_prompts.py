from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.database.repositories.prompt_repo import PromptRepository

router = APIRouter(prefix="/system-prompts", tags=["System Prompts"])

class CreateSystemPromptRequest(BaseModel):
    name: str
    content: str
    is_global: bool = False

class UpdateSystemPromptRequest(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    is_global: Optional[bool] = None
    is_active: Optional[bool] = None

@router.get("")
async def list_prompts():
    return await PromptRepository.list_system_prompts()

@router.post("")
async def create_prompt(req: CreateSystemPromptRequest):
    return await PromptRepository.create_system_prompt(
        name=req.name,
        content=req.content,
        is_global=req.is_global
    )

@router.get("/{pid}")
async def get_prompt(pid: str):
    prompt = await PromptRepository.get_system_prompt(pid)
    if not prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return prompt

@router.patch("/{pid}")
async def update_prompt(pid: str, req: UpdateSystemPromptRequest):
    updates = req.model_dump(exclude_unset=True)
    prompt = await PromptRepository.update_system_prompt(pid, updates)
    if not prompt:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return prompt

@router.delete("/{pid}")
async def delete_prompt(pid: str):
    deleted = await PromptRepository.delete_system_prompt(pid)
    if not deleted:
        raise HTTPException(status_code=404, detail="System prompt not found")
    return {"status": "deleted", "id": pid}
