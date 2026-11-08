from typing import Dict, Any, Optional
import re
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from backend.app.database.repositories.skill_repo import SkillRepository
from backend.app.skills.file_manager import SkillFileManager

router = APIRouter(prefix="/skills", tags=["skills"])

class SkillCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=60)
    command: str = Field(..., min_length=2, max_length=30)
    description: str = Field(..., min_length=5, max_length=250)
    system_prompt: str = Field(..., min_length=5)
    icon: Optional[str] = "sparkles"
    color: Optional[str] = "indigo"

class SkillUpdateRequest(BaseModel):
    name: Optional[str] = None
    command: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None

class SkillImportFileRequest(BaseModel):
    content: str = Field(..., min_length=10)

def attach_file_meta(skill: Dict[str, Any]) -> Dict[str, Any]:
    cmd = (skill.get("command") or "").strip().lstrip("/")
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", cmd) or "skill"
    skill["file_path"] = f"skills/{slug}/SKILL.md"
    return skill

@router.get("", response_model=Dict[str, Any])
async def list_skills():
    skills = await SkillRepository.list_skills()
    enriched = [attach_file_meta(s) for s in skills]
    return {"skills": enriched, "count": len(enriched)}

@router.post("/scan")
async def scan_skills_folder():
    """Scans physical `skills/` workspace folder, importing new or updated SKILL.md files into the database."""
    stats = await SkillFileManager.scan_and_sync()
    skills = await SkillRepository.list_skills()
    enriched = [attach_file_meta(s) for s in skills]
    return {
        "status": "success",
        "message": f"Scanned skills folder. {stats['new_imported']} new skills imported, {stats['updated']} updated.",
        "stats": stats,
        "skills": enriched
    }

@router.post("/import-file", status_code=status.HTTP_201_CREATED)
async def import_skill_file(req: SkillImportFileRequest):
    """Imports a SKILL.md formatted string (with YAML frontmatter) directly into disk and database."""
    parsed = SkillFileManager.parse_skill_markdown(req.content)
    if not parsed or not parsed.get("name") or not parsed.get("command"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid SKILL.md file format. Ensure it contains standard YAML frontmatter with 'name' and 'command'."
        )
    
    cmd = parsed["command"]
    if not cmd.startswith("/"):
        cmd = "/" + cmd
        parsed["command"] = cmd

    existing = await SkillRepository.get_skill_by_command(cmd)
    if existing:
        updated = await SkillRepository.update_skill(existing["id"], parsed)
        SkillFileManager.save_skill_to_disk(updated)
        return {"status": "updated", "skill": attach_file_meta(updated)}

    skill = await SkillRepository.create_skill(
        name=parsed["name"],
        command=parsed["command"],
        description=parsed["description"],
        system_prompt=parsed["system_prompt"],
        icon=parsed.get("icon", "sparkles"),
        color=parsed.get("color", "emerald")
    )
    SkillFileManager.save_skill_to_disk(skill)
    return {"status": "created", "skill": attach_file_meta(skill)}

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_skill(req: SkillCreateRequest):
    # Check if command already exists
    clean_cmd = req.command.strip().lower()
    if not clean_cmd.startswith("/"):
        clean_cmd = "/" + clean_cmd

    existing = await SkillRepository.get_skill_by_command(clean_cmd)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Skill with command '{clean_cmd}' already exists."
        )

    skill = await SkillRepository.create_skill(
        name=req.name,
        command=clean_cmd,
        description=req.description,
        system_prompt=req.system_prompt,
        icon=req.icon or "sparkles",
        color=req.color or "indigo"
    )
    # Persist physical file in skills/ directory
    SkillFileManager.save_skill_to_disk(skill)
    return {"status": "created", "skill": attach_file_meta(skill)}

@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    skill = await SkillRepository.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return attach_file_meta(skill)

@router.put("/{skill_id}")
async def update_skill(skill_id: str, req: SkillUpdateRequest):
    skill = await SkillRepository.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    
    update_data = {k: v for k, v in req.dict(exclude_unset=True).items() if v is not None}
    updated = await SkillRepository.update_skill(skill_id, update_data)
    # Update physical file in skills/ directory
    SkillFileManager.save_skill_to_disk(updated)
    return {"status": "updated", "skill": attach_file_meta(updated)}

@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    skill = await SkillRepository.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    if skill.get("is_builtin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete builtin system skills.")

    success = await SkillRepository.delete_skill(skill_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete skill")

    # Remove physical file from skills/ directory
    SkillFileManager.delete_skill_from_disk(skill.get("command", ""))
    return {"status": "deleted", "id": skill_id}
