from pathlib import Path
from fastapi import APIRouter
from backend.app.core.config import settings

router = APIRouter(prefix="/logs", tags=["Logs & Diagnostics"])

@router.get("/app")
async def get_app_logs(lines: int = 100):
    log_file = settings.LOGS_DIR / "nova.log"
    if not log_file.exists():
        return {"lines": []}
    try:
        content = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        return {"lines": content[-lines:]}
    except Exception as e:
        return {"error": str(e), "lines": []}

@router.get("/audit")
async def get_audit_logs(lines: int = 100):
    audit_file = settings.LOGS_DIR / "audit.log"
    if not audit_file.exists():
        return {"events": []}
    import json
    try:
        content = audit_file.read_text(encoding="utf-8", errors="replace").splitlines()
        events = []
        for l in content[-lines:]:
            if l.strip():
                try:
                    events.append(json.loads(l))
                except Exception:
                    continue
        return {"events": events}
    except Exception as e:
        return {"error": str(e), "events": []}
