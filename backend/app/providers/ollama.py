import json
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
from backend.app.providers.base import BaseProviderAdapter, ProviderCapabilities, StreamChunk
from backend.app.core.logging import logger

class OllamaAdapter(BaseProviderAdapter):
    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            model_discovery=True,
            streaming=True,
            function_calling=True,
            vision=True,
            reasoning=True,
            structured_output=True,
            local=True
        )

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        headers.update(self.custom_headers)
        return headers

    async def test_connection(self) -> Tuple[bool, str, Dict[str, Any]]:
        url = f"{self.base_url}/api/tags"
        try:
            async with self.get_client(timeout=5.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("models", [])
                    return True, f"Ollama is running locally. Found {len(models)} installed models.", {"models_count": len(models)}
                return False, f"Ollama returned HTTP {resp.status_code}", {"status_code": resp.status_code}
        except Exception as e:
            return False, f"Ollama connection failed (is Ollama service running on {self.base_url}?): {str(e)}", {"error": str(e)}

    async def discover_models(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/tags"
        try:
            async with self.get_client(timeout=5.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                if resp.status_code != 200:
                    return []
                data = resp.json()
                models = data.get("models", [])
                result = []
                for m in models:
                    name = m.get("name", "")
                    details = m.get("details", {})
                    result.append({
                        "model_name": name,
                        "display_name": f"{name} ({details.get('parameter_size', 'local')})",
                        "context_length": 8192,
                        "supports_tools": True,
                        "supports_vision": "llava" in name.lower() or "vision" in name.lower(),
                        "is_local": True
                    })
                return result
        except Exception as e:
            logger.warning(f"Ollama discover error: {e}")
            return []

    async def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        enable_thinking: Optional[bool] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        url = f"{self.base_url}/api/chat"
        # Convert messages if needed
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature
            }
        }
        if enable_thinking is not None:
            payload["think"] = bool(enable_thinking)

        if tools:
            # Map tools to Ollama function calling format
            payload["tools"] = tools

        try:
            async with self.get_client() as client:
                async with client.stream("POST", url, json=payload, headers=self._get_headers()) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        yield StreamChunk(delta_text=f"\n[Ollama error {resp.status_code}: {err.decode('utf-8', errors='replace')[:200]}]")
                        return

                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        msg = obj.get("message", {})
                        content = msg.get("content", "")
                        done = obj.get("done", False)

                        # Check tool calls
                        raw_tc = msg.get("tool_calls") or []
                        parsed_tc = []
                        for tc in raw_tc:
                            func = tc.get("function", {})
                            parsed_tc.append({
                                "id": f"ollama_tc_{func.get('name')}",
                                "name": func.get("name", ""),
                                "arguments": json.dumps(func.get("arguments", {}))
                            })

                        chunk = StreamChunk(
                            delta_text=content,
                            tool_calls=parsed_tc,
                            finish_reason="stop" if done else None
                        )
                        yield chunk
        except Exception as e:
            logger.error(f"Error in Ollama chat_stream: {e}")
            yield StreamChunk(delta_text=f"\n[Ollama stream error: {str(e)}]")
