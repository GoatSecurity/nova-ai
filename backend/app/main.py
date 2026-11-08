import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.database.schema import init_db
from backend.app.tools import init_all_tools

# Route imports
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.conversations import router as conv_router
from backend.app.api.routes.providers import router as prov_router
from backend.app.api.routes.agent_profiles import router as profiles_router
from backend.app.api.routes.system_prompts import router as prompts_router
from backend.app.api.routes.tools_routes import router as tools_router
from backend.app.api.routes.approvals import router as approvals_router
from backend.app.api.routes.executions import router as executions_router
from backend.app.api.routes.workspaces import router as workspaces_router
from backend.app.api.routes.memory import router as memory_router
from backend.app.api.routes.settings_routes import router as settings_router
from backend.app.api.routes.attachments import router as attachments_router
from backend.app.api.routes.logs_routes import router as logs_router
from backend.app.api.routes.database_routes import router as db_router
from backend.app.api.routes.ws import router as ws_router
from backend.app.api.routes.skills import router as skills_router
from backend.app.api.routes.mcp_routes import router as mcp_router
from backend.app.mcp.manager import mcp_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} on {settings.HOST}:{settings.PORT}...")
    await init_db()
    init_all_tools()
    try:
        from backend.app.skills.file_manager import SkillFileManager
        await SkillFileManager.scan_and_sync()
    except Exception as e:
        logger.warning(f"Error during Skill files synchronization: {e}")

    try:
        await mcp_manager.init_enabled_servers()
    except Exception as e:
        logger.warning(f"Error during MCP servers initialization: {e}")
    logger.info("NOVA Application Engine is ready.")
    yield
    # Shutdown
    logger.info("NOVA Application shutting down gracefully...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="NOVA: Advanced Local AI Agent & Desktop Automation Platform",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# No-Cache Middleware for fresh frontend asset delivery
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

@app.middleware("http")
async def no_cache_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/c/") or path.endswith(".html") or path.endswith(".js") or path.endswith(".css"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Register API Routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(conv_router, prefix="/api")
app.include_router(prov_router, prefix="/api")
app.include_router(profiles_router, prefix="/api")
app.include_router(prompts_router, prefix="/api")
app.include_router(tools_router, prefix="/api")
app.include_router(approvals_router, prefix="/api")
app.include_router(executions_router, prefix="/api")
app.include_router(workspaces_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(attachments_router, prefix="/api")
app.include_router(logs_router, prefix="/api")
app.include_router(db_router, prefix="/api")
app.include_router(ws_router, prefix="/api")
app.include_router(skills_router, prefix="/api")
app.include_router(mcp_router, prefix="/api")

# Serve frontend build static files if built
static_dist = settings.STATIC_DIR
if static_dist.exists() and (static_dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(static_dist / "assets")), name="assets")

    @app.get("/c/{conv_id}")
    async def serve_conversation_page(conv_id: str):
        return FileResponse(str(static_dist / "index.html"), headers=NO_CACHE_HEADERS)

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept /api routes
        if full_path.startswith("api"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        target = static_dist / full_path
        if target.is_file():
            return FileResponse(str(target), headers=NO_CACHE_HEADERS)
        return FileResponse(str(static_dist / "index.html"), headers=NO_CACHE_HEADERS)
else:
    @app.get("/")
    async def index_dev():
        return {
            "status": "online",
            "message": "NOVA Backend API is running on port 46815. Frontend dist not yet built.",
            "api_docs": "http://127.0.0.1:46815/docs"
        }
