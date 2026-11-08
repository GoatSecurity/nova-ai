import json
import re
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from backend.app.database.repositories.mcp_repo import MCPRepository
from backend.app.mcp.manager import mcp_manager

router = APIRouter(prefix="/mcp", tags=["mcp"])

class MCPServerCreateRequest(BaseModel):
    name: Optional[str] = None
    transport_type: Optional[str] = "http"
    command: Optional[str] = None
    args: Optional[List[str]] = Field(default_factory=list)
    env: Optional[Dict[str, str]] = Field(default_factory=dict)
    url: Optional[str] = None
    config_json: Optional[str] = None
    is_enabled: Optional[int] = 1

class MCPServerUpdateRequest(BaseModel):
    name: Optional[str] = None
    transport_type: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None
    is_enabled: Optional[int] = None

@router.get("/servers", response_model=Dict[str, Any])
async def list_servers():
    servers = await MCPRepository.list_servers()
    return {"servers": servers, "count": len(servers)}

@router.get("/presets", response_model=Dict[str, Any])
async def list_presets():
    return {"presets": mcp_manager.get_presets()}

@router.post("/servers", status_code=status.HTTP_201_CREATED)
async def create_server(req: MCPServerCreateRequest):
    name = (req.name or "").strip()
    url = (req.url or "").strip()
    transport_type = req.transport_type or "http"
    command = (req.command or "").strip()
    args = req.args or []
    env = req.env or {}

    # Support raw config JSON pasting (e.g. {"mcpServers": {"torob": {"url": "..."}}})
    raw_input = req.config_json or name or ""
    if "{" in raw_input and "}" in raw_input:
        try:
            parsed = json.loads(raw_input)
            if "mcpServers" in parsed and isinstance(parsed["mcpServers"], dict):
                first_key = list(parsed["mcpServers"].keys())[0]
                srv_cfg = parsed["mcpServers"][first_key]
                name = first_key
                if "url" in srv_cfg:
                    url = srv_cfg["url"]
                    transport_type = "http"
                elif "command" in srv_cfg:
                    command = srv_cfg.get("command", "")
                    args = srv_cfg.get("args", [])
                    env = srv_cfg.get("env", {})
                    transport_type = "stdio"
            elif "url" in parsed:
                url = parsed["url"]
                transport_type = "http"
                if "name" in parsed:
                    name = parsed["name"]
        except Exception:
            pass

    # If name is a URL or url is present
    if not url and (name.startswith("http://") or name.startswith("https://")):
        url = name
        # Derive friendly name from domain
        match = re.search(r"https?://([^/]+)", url)
        domain = match.group(1) if match else "remote-mcp"
        name = domain.split(".")[0].capitalize()
        transport_type = "http"

    if url:
        transport_type = "http"
        if not name:
            name = "Remote MCP Server"

    if not name:
        name = "Custom MCP Server"

    server = await MCPRepository.create_server(
        name=name,
        transport_type=transport_type,
        command=command,
        args=args,
        env=env,
        url=url,
        is_enabled=req.is_enabled if req.is_enabled is not None else 1
    )

    # If enabled, auto-connect immediately and discover tools
    if server.get("is_enabled"):
        try:
            await mcp_manager.connect_server(server["id"])
            server = await MCPRepository.get_server(server["id"])
        except Exception as e:
            # Server created, but connection encountered an error; stored in last_error
            pass

    return {"status": "created", "server": server}

@router.post("/servers/{server_id}/connect")
async def connect_server(server_id: str):
    server = await MCPRepository.get_server(server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    try:
        res = await mcp_manager.connect_server(server_id)
        return {"status": "connected", "details": res}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/servers/{server_id}/disconnect")
async def disconnect_server(server_id: str):
    server = await MCPRepository.get_server(server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    await mcp_manager.disconnect_server(server_id)
    return {"status": "disconnected", "server_id": server_id}

@router.delete("/servers/{server_id}")
async def delete_server(server_id: str):
    server = await MCPRepository.get_server(server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")

    await mcp_manager.disconnect_server(server_id)
    success = await MCPRepository.delete_server(server_id)
    return {"status": "deleted", "server_id": server_id, "success": success}
