import json
import asyncio
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
from backend.app.providers.base import BaseProviderAdapter, ProviderCapabilities, StreamChunk
from backend.app.core.logging import logger

def clean_model_display_name(raw_name: str) -> str:
    """Cleans file paths and model extensions to provide a short, readable model name."""
    if not raw_name:
        return ""
    cleaned = raw_name.replace("\\", "/").rstrip("/")
    if "/" in cleaned:
        cleaned = cleaned.split("/")[-1]
    for ext in [".gguf", ".bin", ".safetensors", ".pt", ".pth", ".onnx"]:
        if cleaned.lower().endswith(ext):
            cleaned = cleaned[:-len(ext)]
            break
    return cleaned or raw_name

class OpenAICompatibleAdapter(BaseProviderAdapter):
    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            model_discovery=True,
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
            "User-Agent": "NOVA-AI-Workstation/1.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self.custom_headers)
        return headers

    def _get_candidate_models_urls(self) -> List[str]:
        urls = []
        base = self.base_url.rstrip("/")
        # Standard endpoint: e.g. http://127.0.0.1:8080/v1/models
        urls.append(f"{base}{self.models_endpoint}")
        if base.endswith("/v1"):
            # Also try stripped /v1: e.g. http://127.0.0.1:8080/models
            without_v1 = base[:-3].rstrip("/")
            urls.append(f"{without_v1}{self.models_endpoint}")
        else:
            # Also try with /v1: e.g. http://127.0.0.1:8080/v1/models
            urls.append(f"{base}/v1{self.models_endpoint}")
        # Ollama native API fallback if port is 11434
        if "11434" in base:
            urls.append(f"{base.split('/v1')[0]}/api/tags")
        # Deduplicate preserving order
        seen = set()
        deduped = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        return deduped

    async def test_connection(self) -> Tuple[bool, str, Dict[str, Any]]:
        candidate_urls = self._get_candidate_models_urls()
        headers = self._get_headers()
        last_error = "Connection could not be established."
        last_status = None

        for url in candidate_urls:
            try:
                async with self.get_client(timeout=10.0) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        count = 0
                        if isinstance(data, list):
                            count = len(data)
                        elif isinstance(data, dict):
                            raw = data.get("data") or data.get("models") or []
                            count = len(raw) if isinstance(raw, list) else 0
                        return True, f"Successfully connected to {url}! Found {count} models.", {"status_code": 200, "url": url}
                    elif resp.status_code == 401:
                        return False, "Authentication failed: Invalid API key.", {"status_code": 401}
                    else:
                        last_status = resp.status_code
                        last_error = f"HTTP {resp.status_code}: {resp.text[:150]}"
            except Exception as e:
                last_error = str(e)

        return False, f"Connection failed: {last_error}", {"status_code": last_status}

    async def discover_models(self) -> List[Dict[str, Any]]:
        candidate_urls = self._get_candidate_models_urls()
        headers = self._get_headers()
        last_error = None

        for url in candidate_urls:
            try:
                async with self.get_client(timeout=10.0) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code != 200:
                        last_error = f"HTTP {resp.status_code} from {url}"
                        continue
                    data = resp.json()
                    raw_models: List[Any] = []
                    if isinstance(data, list):
                        raw_models = data
                    elif isinstance(data, dict):
                        raw_models = data.get("data") or data.get("models") or data.get("model") or []

                    if not isinstance(raw_models, list) or len(raw_models) == 0:
                        continue

                    normalized = []
                    for m in raw_models:
                        model_id = ""
                        context_len = 8192
                        if isinstance(m, str):
                            model_id = m
                        elif isinstance(m, dict):
                            model_id = m.get("id") or m.get("name") or m.get("model") or ""
                            context_len = m.get("context_window") or m.get("context_length") or 8192

                        if not model_id:
                            continue

                        display_name = clean_model_display_name(model_id)
                        normalized.append({
                            "model_name": model_id,
                            "display_name": display_name,
                            "context_length": context_len,
                            "supports_tools": True,
                            "supports_vision": "vision" in model_id.lower() or "4o" in model_id.lower() or "vl" in model_id.lower() or "llava" in model_id.lower(),
                            "is_local": self.is_local_url()
                        })

                    if normalized:
                        logger.info(f"Successfully discovered {len(normalized)} models from {url}")
                        return normalized
            except Exception as e:
                last_error = str(e)
                logger.debug(f"Could not fetch models from {url}: {e}")

        if last_error:
            logger.warning(f"Failed to discover models for {self.name} ({self.base_url}): {last_error}")
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
        url = f"{self.base_url}{self.chat_endpoint}"
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if enable_thinking is not None:
            is_openai_cloud = "api.openai.com" in self.base_url.lower()
            if not is_openai_cloud:
                payload["chat_template_kwargs"] = {"enable_thinking": bool(enable_thinking)}
                payload["reasoning_format"] = "auto" if enable_thinking else "deepseek"
                if enable_thinking:
                    payload["reasoning_control"] = True
            if enable_thinking:
                payload["reasoning_effort"] = "medium"

        headers = self._get_headers()

        for attempt in range(4):
            accumulated_tools: Dict[int, Dict[str, Any]] = {}
            received_any = False
            try:
                async with self.get_client() as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code != 200:
                            err_body = await response.aread()
                            yield StreamChunk(delta_text=f"\n[Provider API Error {response.status_code}: {err_body.decode('utf-8', errors='replace')[:300]}]")
                            return

                        async for line in response.aiter_lines():
                            if not line or not line.startswith("data:"):
                                continue
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break

                            try:
                                chunk_json = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            choices = chunk_json.get("choices", [])
                            if not choices:
                                continue

                            choice = choices[0]
                            delta = choice.get("delta", {})
                            finish_reason = choice.get("finish_reason")

                            # Text content
                            content = delta.get("content") or ""
                            # Reasoning/thought content (e.g. DeepSeek-R1, OpenAI reasoning)
                            thought = delta.get("reasoning_content") or delta.get("thought") or ""

                            # Tool calls chunk
                            delta_tool_calls = delta.get("tool_calls") or []
                            for tc in delta_tool_calls:
                                idx = tc.get("index", 0)
                                if idx not in accumulated_tools:
                                    accumulated_tools[idx] = {
                                        "id": tc.get("id") or f"tc_{idx}",
                                        "name": "",
                                        "arguments": ""
                                    }
                                if tc.get("id"):
                                    accumulated_tools[idx]["id"] = tc["id"]
                                func = tc.get("function", {})
                                if func.get("name"):
                                    accumulated_tools[idx]["name"] += func["name"]
                                if func.get("arguments"):
                                    accumulated_tools[idx]["arguments"] += func["arguments"]

                            received_any = True
                            yield StreamChunk(
                                delta_text=content,
                                delta_thought=thought,
                                finish_reason=finish_reason
                            )

                if accumulated_tools:
                    parsed_tools = []
                    for _, tc_data in sorted(accumulated_tools.items()):
                        parsed_tools.append({
                            "id": tc_data["id"],
                            "name": tc_data["name"],
                            "arguments": tc_data["arguments"]
                        })
                    yield StreamChunk(tool_calls=parsed_tools, finish_reason="tool_calls")
                break

            except Exception as e:
                if accumulated_tools:
                    parsed_tools = []
                    for _, tc_data in sorted(accumulated_tools.items()):
                        parsed_tools.append({
                            "id": tc_data["id"],
                            "name": tc_data["name"],
                            "arguments": tc_data["arguments"]
                        })
                    yield StreamChunk(tool_calls=parsed_tools, finish_reason="tool_calls")
                    break

                if attempt < 3:
                    backoff = 1.5 * (attempt + 1)
                    logger.warning(f"Retrying chat_stream for {self.name} (attempt {attempt+1}/4) after {type(e).__name__}: {e}. Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                    continue

                logger.error(f"Error in chat_stream ({self.name}): {e}")
                err_detail = str(e).strip() or f"{type(e).__name__}: Stream timed out or dropped by remote host"
                yield StreamChunk(delta_text=f"\n[Stream connection error: {err_detail}]")
                break
