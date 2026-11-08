import os
import re
import yaml
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.database.repositories.skill_repo import SkillRepository

class SkillFileManager:
    """
    Manages physical file-based skills in the `skills/` workspace folder.
    Each skill is stored in standard Markdown with YAML frontmatter:
    skills/<skill-folder>/SKILL.md
    """

    SKILLS_DIR = settings.BASE_DIR / "skills"

    @classmethod
    def get_skills_dir(cls) -> Path:
        cls.SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        return cls.SKILLS_DIR

    @classmethod
    def serialize_skill_markdown(cls, skill: Dict[str, Any]) -> str:
        """Formats skill metadata and system instructions into standard YAML-frontmatter Markdown."""
        frontmatter = {
            "name": skill.get("name", "Unnamed Skill"),
            "command": skill.get("command", "/skill"),
            "description": skill.get("description", ""),
            "icon": skill.get("icon", "sparkles"),
            "color": skill.get("color", "emerald"),
            "is_builtin": bool(skill.get("is_builtin", False))
        }
        yaml_header = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
        body = (skill.get("system_prompt") or "").strip()
        return f"---\n{yaml_header}\n---\n\n{body}\n"

    @classmethod
    def parse_skill_markdown(cls, content: str) -> Optional[Dict[str, Any]]:
        """Parses a SKILL.md file with YAML frontmatter."""
        content = content.strip()
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        try:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            if not isinstance(meta, dict):
                return None
            return {
                "name": meta.get("name", "Custom Skill").strip(),
                "command": meta.get("command", "/skill").strip(),
                "description": meta.get("description", "").strip(),
                "icon": meta.get("icon", "sparkles").strip(),
                "color": meta.get("color", "emerald").strip(),
                "system_prompt": body,
                "is_builtin": bool(meta.get("is_builtin", False))
            }
        except Exception as e:
            logger.warning(f"Error parsing SKILL.md YAML frontmatter: {e}")
            return None

    @classmethod
    def save_skill_to_disk(cls, skill: Dict[str, Any]) -> Path:
        """Writes or updates a skill in skills/<command_slug>/SKILL.md."""
        cmd = skill.get("command", "/skill").strip().lstrip("/")
        folder_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", cmd) or "skill"
        skill_dir = cls.get_skills_dir() / folder_slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        markdown_content = cls.serialize_skill_markdown(skill)
        skill_file.write_text(markdown_content, encoding="utf-8")
        logger.info(f"Persisted skill '{skill.get('name')}' to {skill_file}")
        return skill_file

    @classmethod
    def delete_skill_from_disk(cls, command: str) -> bool:
        """Deletes the skill folder or file for a given command."""
        cmd = command.strip().lstrip("/")
        folder_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", cmd) or "skill"
        skill_dir = cls.get_skills_dir() / folder_slug
        single_file = cls.get_skills_dir() / f"{folder_slug}.md"

        deleted = False
        if skill_dir.exists() and skill_dir.is_dir():
            shutil.rmtree(skill_dir, ignore_errors=True)
            deleted = True
        if single_file.exists():
            single_file.unlink(missing_ok=True)
            deleted = True
        return deleted

    @classmethod
    async def scan_and_sync(cls) -> Dict[str, Any]:
        """
        Scans skills/ directory on disk, imports any new/modified SKILL.md files into SQLite,
        and ensures all DB skills exist on disk.
        """
        skills_dir = cls.get_skills_dir()
        scanned_count = 0
        added_count = 0
        updated_count = 0

        # 1. Scan disk files
        for root, dirs, files in os.walk(skills_dir):
            for f in files:
                if f.upper() in ("SKILL.MD",) or (f.endswith(".md") and root == str(skills_dir)):
                    p = Path(root) / f
                    try:
                        content = p.read_text(encoding="utf-8")
                        parsed = cls.parse_skill_markdown(content)
                        if parsed and parsed.get("name") and parsed.get("command"):
                            scanned_count += 1
                            cmd = parsed["command"]
                            if not cmd.startswith("/"):
                                cmd = "/" + cmd
                                parsed["command"] = cmd

                            existing = await SkillRepository.get_skill_by_command(cmd)
                            if existing:
                                # Keep synced when SKILL.md metadata or prompt changed on disk
                                needs_sync = (
                                    not existing.get("is_builtin")
                                    or existing.get("system_prompt") != parsed["system_prompt"]
                                    or existing.get("description") != parsed["description"]
                                )
                                if needs_sync:
                                    await SkillRepository.update_skill(existing["id"], parsed)
                                    updated_count += 1
                            else:
                                await SkillRepository.create_skill(
                                    name=parsed["name"],
                                    command=parsed["command"],
                                    description=parsed["description"],
                                    system_prompt=parsed["system_prompt"],
                                    icon=parsed.get("icon", "sparkles"),
                                    color=parsed.get("color", "emerald")
                                )
                                added_count += 1
                    except Exception as err:
                        logger.warning(f"Failed scanning skill file {p}: {err}")

        # 2. Export DB skills to disk if missing
        db_skills = await SkillRepository.list_skills()
        for s in db_skills:
            cmd = s.get("command", "").strip().lstrip("/")
            folder_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", cmd) or "skill"
            target_file = skills_dir / folder_slug / "SKILL.md"
            if not target_file.exists():
                cls.save_skill_to_disk(s)

        return {
            "scanned_files": scanned_count,
            "new_imported": added_count,
            "updated": updated_count,
            "total_skills": len(db_skills)
        }
