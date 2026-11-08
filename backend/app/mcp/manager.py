import asyncio
import json
import re
from typing import Dict, Any, List, Optional
from backend.app.core.logging import logger
from backend.app.tools.base import BaseTool, ToolParameter
from backend.app.tools.registry import tool_registry
from backend.app.mcp.client import MCPClient
from backend.app.database.repositories.mcp_repo import MCPRepository

class MCPManager:
    """
    Coordinates external Model Context Protocol (MCP) servers.
    Supports both:
    - Remote HTTP/SSE endpoint servers
    - Local child processes (stdio with command, args, and environment variables)
    Dynamically discovers tools and registers them into the NOVA Agentic Tool Registry.
    """
    _instance: Optional["MCPManager"] = None

    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        self.registered_tool_names: Dict[str, List[str]] = {}

    @classmethod
    def get_instance(cls) -> "MCPManager":
        if cls._instance is None:
            cls._instance = MCPManager()
        return cls._instance

    @staticmethod
    def get_presets() -> List[Dict[str, Any]]:
        # Clean, empty presets by default — user can add custom Remote or Local MCP servers
        return []

    async def connect_server(self, server_id: str) -> Dict[str, Any]:
        """Connects to an MCP server (Remote HTTP or Local stdio) and registers discovered tools."""
        server = await MCPRepository.get_server(server_id)
        if not server:
            raise ValueError(f"MCP server '{server_id}' not found.")

        # Disconnect existing if active
        if server_id in self.clients:
            await self.disconnect_server(server_id)

        client = MCPClient(server_id, server)
        try:
            tools = await client.connect(timeout=25.0)
            self.clients[server_id] = client

            # Register tools in NOVA Tool Registry
            clean_srv_name = re.sub(r"[^a-zA-Z0-9_]+", "_", server["name"].lower()).strip("_")
            reg_names = []

            for t in tools:
                raw_name = t.get("name", "unnamed_tool")
                safe_name = f"mcp_{clean_srv_name}_{raw_name}"
                schema = t.get("inputSchema") or {}
                properties = schema.get("properties") or {}
                required_fields = schema.get("required") or []

                params = []
                for p_name, p_spec in properties.items():
                    p_type = p_spec.get("type", "string")
                    params.append(ToolParameter(
                        name=p_name,
                        type=p_type,
                        description=p_spec.get("description", f"Parameter {p_name}"),
                        required=(p_name in required_fields),
                        default=p_spec.get("default")
                    ))

                tool_desc = t.get("description") or t.get("title") or ""
                full_desc = f"[MCP: {server['name']}] {tool_desc}".strip()

                tool_obj = BaseTool(
                    name=safe_name,
                    description=full_desc,
                    category="mcp",
                    risk_level="LOW",
                    requires_approval=False,
                    parameters=params
                )

                # Create closure handler
                async def _make_handler(cl: MCPClient, orig_tool_name: str):
                    async def _handler(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
                        return await cl.call_tool(orig_tool_name, args)
                    return _handler

                handler_func = await _make_handler(client, raw_name)
                tool_registry.register(tool_obj, handler_func)
                reg_names.append(safe_name)

                # Also register under direct raw_name if not colliding with native tools
                if raw_name not in tool_registry._tools and raw_name != safe_name:
                    raw_tool_obj = BaseTool(
                        name=raw_name,
                        description=full_desc,
                        category="mcp",
                        risk_level="LOW",
                        requires_approval=False,
                        parameters=params
                    )
                    tool_registry.register(raw_tool_obj, handler_func)
                    reg_names.append(raw_name)

            self.registered_tool_names[server_id] = reg_names

            await MCPRepository.update_server(server_id, {
                "status": "connected",
                "last_error": "",
                "tools_count": len(tools),
                "tools_json": json.dumps(tools)
            })

            logger.info(f"Registered {len(reg_names)} tool endpoints for MCP server '{server['name']}'.")

            return {
                "server_id": server_id,
                "status": "connected",
                "tools_count": len(tools),
                "tools": tools
            }
        except Exception as e:
            err_msg = str(e) or type(e).__name__
            logger.error(f"Failed to connect MCP server '{server_id}': {err_msg}")
            await client.disconnect()
            await MCPRepository.update_server(server_id, {
                "status": "error",
                "last_error": err_msg,
                "tools_count": 0
            })
            raise RuntimeError(f"Connection failed: {err_msg}")

    async def disconnect_server(self, server_id: str):
        """Disconnects an active MCP server and unregisters its tools."""
        if server_id in self.clients:
            client = self.clients.pop(server_id)
            await client.disconnect()

        # Unregister tools from registry
        if server_id in self.registered_tool_names:
            tool_names = self.registered_tool_names.pop(server_id)
            for t_name in tool_names:
                if t_name in tool_registry._tools:
                    del tool_registry._tools[t_name]
                if t_name in tool_registry._handlers:
                    del tool_registry._handlers[t_name]
            logger.info(f"Unregistered {len(tool_names)} tools for MCP server '{server_id}'.")

        await MCPRepository.update_server(server_id, {
            "status": "disconnected",
            "last_error": ""
        })

    async def register_cached_tools(self, server: Dict[str, Any], tools: List[Dict[str, Any]]):
        """Restores tools directly from database cache without making blocking network requests."""
        server_id = server["id"]
        clean_srv_name = re.sub(r"[^a-zA-Z0-9_]+", "_", server["name"].lower()).strip("_")
        reg_names = []

        for t in tools:
            raw_name = t.get("name", "unnamed_tool")
            safe_name = f"mcp_{clean_srv_name}_{raw_name}"
            schema = t.get("inputSchema") or {}
            properties = schema.get("properties") or {}
            required_fields = schema.get("required") or []

            params = []
            for p_name, p_spec in properties.items():
                p_type = p_spec.get("type", "string")
                params.append(ToolParameter(
                    name=p_name,
                    type=p_type,
                    description=p_spec.get("description", f"Parameter {p_name}"),
                    required=(p_name in required_fields),
                    default=p_spec.get("default")
                ))

            tool_desc = t.get("description") or t.get("title") or ""
            full_desc = f"[MCP: {server['name']}] {tool_desc}".strip()

            tool_obj = BaseTool(
                name=safe_name,
                description=full_desc,
                category="mcp",
                risk_level="LOW",
                requires_approval=False,
                parameters=params
            )

            async def _make_lazy_handler(srv_id: str, orig_name: str):
                async def _handler(args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
                    if srv_id not in self.clients:
                        srv = await MCPRepository.get_server(srv_id)
                        if not srv:
                            raise RuntimeError(f"MCP server '{srv_id}' not found.")
                        cl = MCPClient(srv_id, srv)
                        await cl.connect(timeout=20.0)
                        self.clients[srv_id] = cl
                    return await self.clients[srv_id].call_tool(orig_name, args)
                return _handler

            handler_func = await _make_lazy_handler(server_id, raw_name)
            tool_registry.register(tool_obj, handler_func)
            reg_names.append(safe_name)

            if raw_name not in tool_registry._tools and raw_name != safe_name:
                raw_tool_obj = BaseTool(
                    name=raw_name,
                    description=full_desc,
                    category="mcp",
                    risk_level="LOW",
                    requires_approval=False,
                    parameters=params
                )
                tool_registry.register(raw_tool_obj, handler_func)
                reg_names.append(raw_name)

        self.registered_tool_names[server_id] = reg_names

    async def init_enabled_servers(self):
        """Restores registered MCP tools from DB cache on application startup without network latency."""
        servers = await MCPRepository.list_servers()
        for s in servers:
            if s.get("is_enabled"):
                tools = s.get("tools") or []
                if tools:
                    await self.register_cached_tools(s, tools)

mcp_manager = MCPManager.get_instance()
