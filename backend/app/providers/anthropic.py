import json
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
from backend.app.providers.base import BaseProviderAdapter, ProviderCapabilities, StreamChunk
from backend.app.core.logging import logger

class AnthropicAdapter(BaseProviderAdapter):
    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            model_discovery=False,
            streaming=True,
            function_calling=True,
            vision=True,
            reasoning=True,
            structured_output=True,
            local=False
        )

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        headers.update(self.custom_headers)
        return headers

    async def test_connection(self) -> Tuple[bool, str, Dict[str, Any]]:
        # Anthropic doesn't have an open models list endpoint without auth, test with simple token request or status
        url = f"{self.base_url}/messages"
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "ping"}]
        }
        try:
            async with self.get_client(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=self._get_headers())
                if resp.status_code == 200:
                    return True, "Successfully verified Anthropic API credentials.", {"status_code": 200}
                elif resp.status_code == 401:
                    return False, "Anthropic authentication failed: Invalid API key.", {"status_code": 401}
                else:
                    return False, f"Anthropic returned HTTP {resp.status_code}: {resp.text[:200]}", {"status_code": resp.status_code}
        except Exception as e:
            return False, f"Anthropic connection error: {str(e)}", {"error": str(e)}

    async def discover_models(self) -> List[Dict[str, Any]]:
        # Anthropic known standard models catalog
        return [
            {"model_name": "claude-3-7-sonnet-20250219", "display_name": "Claude 3.7 Sonnet (Hybrid Reasoning)", "context_length": 200000, "supports_tools": True, "supports_vision": True, "is_local": False},
            {"model_name": "claude-3-5-sonnet-20241022", "display_name": "Claude 3.5 Sonnet", "context_length": 200000, "supports_tools": True, "supports_vision": True, "is_local": False},
            {"model_name": "claude-3-5-haiku-20241022", "display_name": "Claude 3.5 Haiku", "context_length": 200000, "supports_tools": True, "supports_vision": False, "is_local": False},
            {"model_name": "claude-3-opus-20240229", "display_name": "Claude 3 Opus", "context_length": 200000, "supports_tools": True, "supports_vision": True, "is_local": False}
        ]

    async def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        enable_thinking: Optional[bool] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        url = f"{self.base_url}/messages"

        # Separate system messages and convert multimodal image parts
        system_prompt = ""
        filtered_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_prompt += str(m.get("content", "")) + "\n\n"
            else:
                c = m.get("content")
                if isinstance(c, list):
                    anthropic_parts = []
                    for p in c:
                        if isinstance(p, dict):
                            p_type = p.get("type")
                            if p_type == "text":
                                anthropic_parts.append({"type": "text", "text": p.get("text", "")})
                            elif p_type == "image_url":
                                url = p.get("image_url", {}).get("url", "")
                                if url.startswith("data:"):
                                    try:
                                        header, b64_data = url.split(",", 1)
                                        mime = header.split(";")[0].replace("data:", "").strip()
                                        anthropic_parts.append({
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": mime or "image/png",
                                                "data": b64_data
                                            }
                                        })
                                    except Exception:
                                        pass
                        elif isinstance(p, str):
                            anthropic_parts.append({"type": "text", "text": p})
                    filtered_messages.append({"role": m.get("role", "user"), "content": anthropic_parts})
                else:
                    filtered_messages.append(m)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": True
        }
        if system_prompt.strip():
            payload["system"] = system_prompt.strip()

        if tools:
            anthropic_tools = []
            for t in tools:
                fn = t.get("function", {})
                anthropic_tools.append({
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}})
                })
            payload["tools"] = anthropic_tools

        accumulated_tools: Dict[int, Dict[str, Any]] = {}

        try:
            async with self.get_client() as client:
                async with client.stream("POST", url, json=payload, headers=self._get_headers()) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        yield StreamChunk(delta_text=f"\n[Anthropic error {resp.status_code}: {err.decode('utf-8', errors='replace')[:250]}]")
                        return

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        etype = event.get("type")
                        if etype == "content_block_start":
                            block = event.get("content_block", {})
                            if block.get("type") == "tool_use":
                                idx = event.get("index", 0)
                                accumulated_tools[idx] = {
                                    "id": block.get("id"),
                                    "name": block.get("name"),
                                    "arguments": ""
                                }
                        elif etype == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield StreamChunk(delta_text=delta.get("text", ""))
                            elif delta.get("type") == "input_json_delta":
                                idx = event.get("index", 0)
                                if idx in accumulated_tools:
                                    accumulated_tools[idx]["arguments"] += delta.get("partial_json", "")
                            elif delta.get("type") == "thinking_delta":
                                yield StreamChunk(delta_thought=delta.get("thinking", ""))

            if accumulated_tools:
                tools_list = list(accumulated_tools.values())
                yield StreamChunk(tool_calls=tools_list, finish_reason="tool_calls")

        except Exception as e:
            logger.error(f"Anthropic stream error: {e}")
            err_detail = str(e).strip() or f"{type(e).__name__}: Stream timed out or dropped by remote host"
            yield StreamChunk(delta_text=f"\n[Anthropic stream connection error: {err_detail}]")
