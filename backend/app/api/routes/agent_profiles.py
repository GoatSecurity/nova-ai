from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.database.repositories.prompt_repo import PromptRepository

router = APIRouter(prefix="/agent-profiles", tags=["Agent Profiles"])

class CreateProfileRequest(BaseModel):
    name: str
    description: str = ""
    system_instructions: str
    preferred_tools: Optional[List[str]] = None
    default_risk_mode: str = "allow_safe"

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_instructions: Optional[str] = None
    preferred_tools: Optional[List[str]] = None
    default_risk_mode: Optional[str] = None

@router.get("")
async def list_profiles():
    return await PromptRepository.list_agent_profiles()

@router.post("")
async def create_profile(req: CreateProfileRequest):
    return await PromptRepository.create_agent_profile(
        name=req.name,
        description=req.description,
        system_instructions=req.system_instructions,
        preferred_tools=req.preferred_tools,
        default_risk_mode=req.default_risk_mode
    )

@router.get("/{pid}")
async def get_profile(pid: str):
    profile = await PromptRepository.get_agent_profile(pid)
    if not profile:
        raise HTTPException(status_code=404, detail="Agent profile not found")
    return profile

@router.patch("/{pid}")
async def update_profile(pid: str, req: UpdateProfileRequest):
    updates = req.model_dump(exclude_unset=True)
    profile = await PromptRepository.update_agent_profile(pid, updates)
    if not profile:
        raise HTTPException(status_code=404, detail="Agent profile not found")
    return profile

@router.delete("/{pid}")
async def delete_profile(pid: str):
    deleted = await PromptRepository.delete_agent_profile(pid)
    if not deleted:
        raise HTTPException(status_code=400, detail="Cannot delete builtin or non-existent profile")
    return {"status": "deleted", "id": pid}
