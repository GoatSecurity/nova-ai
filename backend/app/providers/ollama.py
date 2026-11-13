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

    def _get_candidate_tags_urls(self) -> List[str]:
        base = self.base_url.rstrip("/")
        clean_base = base.split('/v1')[0].rstrip('/')
        urls = [
            f"{clean_base}/api/tags",
            f"{base}/api/tags",
            f"{base}/models",
            f"{clean_base}/v1/models",
            f"{clean_base}/models"
        ]
        seen = set()
        return [u for u in urls if not (u in seen or seen.add(u))]

    async def test_connection(self) -> Tuple[bool, str, Dict[str, Any]]:
        candidate_urls = self._get_candidate_tags_urls()
        last_error = "Connection could not be established."
        last_status = None
        for url in candidate_urls:
            try:
                async with self.get_client(timeout=5.0) as client:
                    resp = await client.get(url, headers=self._get_headers())
                    if resp.status_code == 200:
                        data = resp.json()
                        models = data.get("models") or data.get("data") or []
                        return True, f"Ollama/Model service is online. Found {len(models)} installed models.", {"models_count": len(models)}
                    last_status = resp.status_code
                    last_error = f"HTTP {resp.status_code}"
            except Exception as e:
                last_error = str(e)
        return False, f"Connection failed: {last_error}", {"status_code": last_status}

    async def discover_models(self) -> List[Dict[str, Any]]:
        candidate_urls = self._get_candidate_tags_urls()
        for url in candidate_urls:
            try:
                async with self.get_client(timeout=5.0) as client:
                    resp = await client.get(url, headers=self._get_headers())
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    models = data.get("models") or data.get("data") or []
                    if not isinstance(models, list) or len(models) == 0:
                        continue
                    result = []
                    for m in models:
                        name = ""
                        details = {}
                        caps = []
                        if isinstance(m, str):
                            name = m
                        elif isinstance(m, dict):
                            name = m.get("name") or m.get("model") or m.get("id") or ""
                            details = m.get("details", {})
                            caps = m.get("capabilities", [])
                        if not name:
                            continue

                        has_vis = False
                        if caps and any(str(c).lower() in ("multimodal", "vision", "image") for c in caps):
                            has_vis = True
                        elif caps and any(str(c).lower() in ("completion", "chat", "text") for c in caps):
                            has_vis = False
                        else:
                            has_vis = any(k in name.lower() for k in ["llava", "vision", "vl", "minicpm", "bakllava", "internvl", "clip", "multimodal", "omni", "llama-3.2"])

                        p_size = details.get('parameter_size') or 'local'
                        disp = f"{name} ({p_size})" if p_size != 'local' else name
                        result.append({
                            "model_name": name,
                            "display_name": disp,
                            "context_length": 8192,
                            "supports_tools": True,
                            "supports_vision": has_vis,
                            "is_local": True
                        })
                    if result:
                        return result
            except Exception as e:
                logger.debug(f"Ollama candidate url error ({url}): {e}")
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
        converted_messages = []
        for m in messages:
            c = m.get("content")
            if isinstance(c, list):
                text_parts = []
                image_parts = []
                for p in c:
                    if isinstance(p, dict):
                        p_type = p.get("type")
                        if p_type == "text":
                            text_parts.append(p.get("text", ""))
                        elif p_type == "image_url":
                            img_data_url = p.get("image_url", {}).get("url", "")
                            if img_data_url.startswith("data:"):
                                try:
                                    _, b64_data = img_data_url.split(",", 1)
                                    image_parts.append(b64_data)
                                except Exception:
                                    pass
                            elif img_data_url:
                                image_parts.append(img_data_url)
                    elif isinstance(p, str):
                        text_parts.append(p)
                m_copy = {
                    "role": m.get("role", "user"),
                    "content": "\n".join(text_parts)
                }
                if image_parts:
                    m_copy["images"] = image_parts
                converted_messages.append(m_copy)
            else:
                converted_messages.append(m)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
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
