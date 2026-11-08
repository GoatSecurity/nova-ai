import asyncio
import json
import os
import sys
import shutil
from typing import Dict, Any, List, Optional
import httpx
from backend.app.core.logging import logger

class MCPClient:
    """
    Standard Model Context Protocol (MCP) Client.
    Supports both:
    1. Remote HTTP / SSE MCP servers (stateless JSON-RPC over HTTP)
    2. Local stdio child-process servers (node / python / npx / uvx subprocesses)
    """
    def __init__(self, server_id: str, config: Dict[str, Any]):
        self.server_id = server_id
        self.config = config
        self.url = (config.get("url") or "").strip()
        self.transport_type = config.get("transport_type", "http" if self.url else "stdio")
        if self.url and self.transport_type == "stdio":
            self.transport_type = "http"

        self.process: Optional[asyncio.subprocess.Process] = None
        self._msg_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self.is_connected = False
        self.discovered_tools: List[Dict[str, Any]] = []

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    @staticmethod
    def _parse_http_mcp_response(response_text: str) -> Dict[str, Any]:
        """Parses both standard JSON and Server-Sent Events (SSE) data: payloads."""
        trimmed = response_text.strip()
        if "data:" in trimmed:
            for line in trimmed.split("\n"):
                line = line.strip()
                if line.startswith("data:"):
                    json_str = line[5:].strip()
                    try:
                        return json.loads(json_str)
                    except Exception:
                        continue
        return json.loads(trimmed)

    async def connect(self, timeout: float = 25.0) -> List[Dict[str, Any]]:
        """Connects and discovers tools."""
        if self.transport_type in ("http", "sse", "remote") or self.url:
            return await self._connect_http(timeout=timeout)
        elif self.transport_type == "stdio":
            return await self._connect_stdio(timeout=timeout)
        else:
            raise ValueError(f"Unsupported transport type: {self.transport_type}")

    async def _connect_http(self, timeout: float = 25.0) -> List[Dict[str, Any]]:
        """Discovers tools on a remote HTTP / SSE MCP server."""
        if not self.url:
            raise ValueError(f"No endpoint URL configured for HTTP MCP server '{self.server_id}'.")

        logger.info(f"Connecting to Remote HTTP MCP server '{self.server_id}' at {self.url}...")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NOVA-Workstation/1.0"
        }

        # Optional custom headers or auth from env
        custom_env = self.config.get("env") or {}
        if isinstance(custom_env, dict):
            for k, v in custom_env.items():
                if k.upper().startswith("HEADER_") or k.upper().startswith("AUTH_"):
                    hdr_key = k[7:] if k.upper().startswith("HEADER_") else "Authorization"
                    headers[hdr_key] = str(v)

        async with httpx.AsyncClient(trust_env=False, timeout=timeout, follow_redirects=True) as client:
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": {}
            }
            try:
                resp = await client.post(self.url, json=payload, headers=headers)
                resp.raise_for_status()
                data = self._parse_http_mcp_response(resp.text)
            except Exception as ex:
                logger.info(f"Direct tools/list on '{self.server_id}' returned {ex}; attempting initialize...")
                init_payload = {
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "clientInfo": {"name": "NOVA-Workstation", "version": "1.0.0"}
                    }
                }
                resp_init = await client.post(self.url, json=init_payload, headers=headers)
                resp_init.raise_for_status()
                resp = await client.post(self.url, json=payload, headers=headers)
                resp.raise_for_status()
                data = self._parse_http_mcp_response(resp.text)

            if "error" in data:
                err_msg = data["error"].get("message", "Unknown MCP error")
                raise RuntimeError(f"MCP server returned error: {err_msg}")

            result = data.get("result", {})
            self.discovered_tools = result.get("tools", [])
            self.is_connected = True
            logger.info(f"Remote MCP server '{self.server_id}' connected. Discovered {len(self.discovered_tools)} tools.")
            return self.discovered_tools

    async def _connect_stdio(self, timeout: float = 15.0) -> List[Dict[str, Any]]:
        raw_cmd = self.config.get("command", "").strip()
        args = self.config.get("args", [])
        env = os.environ.copy()
        custom_env = self.config.get("env", {})
        if custom_env and isinstance(custom_env, dict):
            env.update({str(k): str(v) for k, v in custom_env.items()})

        if not raw_cmd:
            raise ValueError("No command specified for stdio MCP server.")

        cmd = raw_cmd
        if sys.platform == "win32":
            resolved = shutil.which(raw_cmd)
            if resolved:
                cmd = resolved
            elif os.path.exists(raw_cmd + ".cmd"):
                cmd = raw_cmd + ".cmd"
            elif os.path.exists(raw_cmd + ".exe"):
                cmd = raw_cmd + ".exe"

        full_cmd = [cmd] + [str(a) for a in args]
        logger.info(f"Launching stdio MCP server: {' '.join(full_cmd)}")

        self.process = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        self._reader_task = asyncio.create_task(self._stdio_reader_loop())

        # Send initialize
        init_res = await self._send_stdio_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "NOVA-Workstation", "version": "1.0.0"}
            },
            timeout=timeout
        )
        logger.info(f"MCP server '{self.server_id}' initialized: {init_res.get('serverInfo', {})}")

        # Send initialized notification
        await self._send_stdio_notification("notifications/initialized", {})

        # List tools
        tools_res = await self._send_stdio_request("tools/list", {}, timeout=timeout)
        self.discovered_tools = tools_res.get("tools", [])
        self.is_connected = True
        logger.info(f"MCP server '{self.server_id}' discovered {len(self.discovered_tools)} tools.")
        return self.discovered_tools

    async def _stdio_reader_loop(self):
        try:
            while self.process and self.process.stdout:
                line = await self.process.stdout.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="ignore").strip()
                if not line_str:
                    continue
                try:
                    msg = json.loads(line_str)
                    req_id = msg.get("id")
                    if req_id is not None and req_id in self._pending_requests:
                        future = self._pending_requests.pop(req_id)
                        if not future.done():
                            if "error" in msg:
                                future.set_exception(RuntimeError(msg["error"].get("message", "MCP error")))
                            else:
                                future.set_result(msg.get("result", {}))
                except json.JSONDecodeError:
                    pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"MCP stdio reader exception for '{self.server_id}': {e}")
        finally:
            self.is_connected = False

    async def _send_stdio_request(self, method: str, params: Dict[str, Any], timeout: float = 15.0) -> Dict[str, Any]:
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP process stdin not open.")

        req_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending_requests[req_id] = fut

        line_bytes = json.dumps(payload).encode("utf-8") + b"\n"
        self.process.stdin.write(line_bytes)
        await self.process.stdin.drain()

        return await asyncio.wait_for(fut, timeout=timeout)

    async def _send_stdio_notification(self, method: str, params: Dict[str, Any]):
        if not self.process or not self.process.stdin:
            return
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        line_bytes = json.dumps(payload).encode("utf-8") + b"\n"
        self.process.stdin.write(line_bytes)
        await self.process.stdin.drain()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 35.0) -> Dict[str, Any]:
        """Calls a tool on the MCP server (supporting both HTTP and stdio)."""
        logger.info(f"Calling MCP tool '{tool_name}' on server '{self.server_id}' with args: {arguments}")
        if self.transport_type in ("http", "sse", "remote") or self.url:
            return await self._call_tool_http(tool_name, arguments, timeout=timeout)
        else:
            return await self._call_tool_stdio(tool_name, arguments, timeout=timeout)

    async def _call_tool_http(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 35.0) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NOVA-Workstation/1.0"
        }
        custom_env = self.config.get("env") or {}
        if isinstance(custom_env, dict):
            for k, v in custom_env.items():
                if k.upper().startswith("HEADER_") or k.upper().startswith("AUTH_"):
                    hdr_key = k[7:] if k.upper().startswith("HEADER_") else "Authorization"
                    headers[hdr_key] = str(v)

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        async with httpx.AsyncClient(trust_env=False, timeout=timeout, follow_redirects=True) as client:
            resp = await client.post(self.url, json=payload, headers=headers)
            resp.raise_for_status()
            data = self._parse_http_mcp_response(resp.text)

        if "error" in data:
            return {
                "tool_name": tool_name,
                "result": data["error"].get("message", "Error in MCP call"),
                "is_error": True
            }

        res = data.get("result", {})
        content_items = res.get("content", [])
        texts = []
        for c in content_items:
            if isinstance(c, dict) and c.get("type") == "text":
                texts.append(c.get("text", ""))
            elif isinstance(c, str):
                texts.append(c)

        full_text = "\n".join(texts) if texts else json.dumps(res, ensure_ascii=False)
        return {
            "tool_name": tool_name,
            "result": full_text,
            "is_error": res.get("isError", False)
        }

    async def _call_tool_stdio(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 35.0) -> Dict[str, Any]:
        res = await self._send_stdio_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments
            },
            timeout=timeout
        )
        content_items = res.get("content", [])
        texts = []
        for c in content_items:
            if isinstance(c, dict) and c.get("type") == "text":
                texts.append(c.get("text", ""))
            elif isinstance(c, str):
                texts.append(c)
        full_text = "\n".join(texts) if texts else json.dumps(res, ensure_ascii=False)
        return {
            "tool_name": tool_name,
            "result": full_text,
            "is_error": res.get("isError", False)
        }

    async def disconnect(self):
        self.is_connected = False
        if self._reader_task:
            self._reader_task.cancel()
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None
        for fut in self._pending_requests.values():
            if not fut.done():
                fut.cancel()
        self._pending_requests.clear()
        logger.info(f"MCP server '{self.server_id}' disconnected cleanly.")
