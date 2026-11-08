import platform
from fastapi import APIRouter
from backend.app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
async def get_health():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "os": platform.system(),
        "port": settings.PORT,
        "permission_mode": settings.DEFAULT_PERMISSION_MODE
    }
