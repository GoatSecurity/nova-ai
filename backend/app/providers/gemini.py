import json
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
from backend.app.providers.base import BaseProviderAdapter, ProviderCapabilities, StreamChunk
from backend.app.core.logging import logger

class GeminiAdapter(BaseProviderAdapter):
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

    async def test_connection(self) -> Tuple[bool, str, Dict[str, Any]]:
        url = f"{self.base_url}/v1beta/models?key={self.api_key}"
        try:
            async with self.get_client(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("models", [])
                    return True, f"Connected to Gemini API. Found {len(models)} models.", {"count": len(models)}
                elif resp.status_code == 400 or resp.status_code == 403:
                    return False, f"Gemini API authentication failed: {resp.text[:200]}", {"status": resp.status_code}
                return False, f"Gemini returned HTTP {resp.status_code}", {"status": resp.status_code}
        except Exception as e:
            return False, f"Gemini connection failed: {str(e)}", {"error": str(e)}

    async def discover_models(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/v1beta/models?key={self.api_key}"
        try:
            async with self.get_client(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return [
                        {"model_name": "gemini-2.0-flash", "display_name": "Gemini 2.0 Flash", "context_length": 1000000, "supports_tools": True, "supports_vision": True, "is_local": False},
                        {"model_name": "gemini-1.5-pro", "display_name": "Gemini 1.5 Pro", "context_length": 2000000, "supports_tools": True, "supports_vision": True, "is_local": False}
                    ]
                data = resp.json()
                models = data.get("models", [])
                result = []
                for m in models:
                    name = m.get("name", "").replace("models/", "")
                    if "gemini" in name:
                        result.append({
                            "model_name": name,
                            "display_name": m.get("displayName", name),
                            "context_length": m.get("inputTokenLimit", 1000000),
                            "supports_tools": True,
                            "supports_vision": True,
                            "is_local": False
                        })
                return result
        except Exception:
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
        url = f"{self.base_url}/v1beta/models/{model}:streamGenerateContent?key={self.api_key}&alt=sse"

        # Transform messages to Gemini contents format
        raw_contents = []
        system_instruction = None

        first_system = True
        for m in messages:
            role = m.get("role", "")
            content = m.get("content") or ""
            if role == "system":
                if first_system:
                    system_instruction = {"parts": [{"text": content}]}
                    first_system = False
                else:
                    # Tool feedbacks and secondary system messages become user turns in Gemini
                    raw_contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "user":
                if isinstance(content, list):
                    gemini_parts = []
                    for p in content:
                        if isinstance(p, dict):
                            p_type = p.get("type")
                            if p_type == "text":
                                gemini_parts.append({"text": p.get("text", "")})
                            elif p_type == "image_url":
                                url = p.get("image_url", {}).get("url", "")
                                if url.startswith("data:"):
                                    try:
                                        header, b64_data = url.split(",", 1)
                                        mime = header.split(";")[0].replace("data:", "").strip()
                                        gemini_parts.append({
                                            "inline_data": {
                                                "mime_type": mime or "image/png",
                                                "data": b64_data
                                            }
                                        })
                                    except Exception:
                                        pass
                        elif isinstance(p, str):
                            gemini_parts.append({"text": p})
                    raw_contents.append({"role": "user", "parts": gemini_parts})
                else:
                    raw_contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                raw_contents.append({"role": "model", "parts": [{"text": content}]})
            elif role in ("tool", "function"):
                raw_contents.append({"role": "user", "parts": [{"text": f"[Tool Output]: {content}"}]})

        # Merge adjacent turns with identical roles (Gemini requires strictly alternating user/model)
        merged_contents = []
        for item in raw_contents:
            if not merged_contents:
                merged_contents.append(item)
            elif merged_contents[-1]["role"] == item["role"]:
                merged_contents[-1]["parts"].extend(item["parts"])
            else:
                merged_contents.append(item)

        # Gemini requires contents to start with user turn
        if merged_contents and merged_contents[0]["role"] == "model":
            merged_contents.insert(0, {"role": "user", "parts": [{"text": "Hello"}]})

        # Gemini requires contents to NOT end with model turn (prevents error 400 invalid_message_role)
        if merged_contents and merged_contents[-1]["role"] == "model":
            merged_contents.append({"role": "user", "parts": [{"text": "Please continue and provide your findings."}]})

        payload: Dict[str, Any] = {
            "contents": merged_contents,
            "generationConfig": {
                "temperature": temperature
            }
        }
        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        if tools:
            func_declarations = []
            for t in tools:
                fn = t.get("function", {})
                func_declarations.append({
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {})
                })
            payload["tools"] = [{"functionDeclarations": func_declarations}]

        try:
            async with self.get_client() as client:
                async with client.stream("POST", url, json=payload) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        yield StreamChunk(delta_text=f"\n[Gemini error {resp.status_code}: {err.decode('utf-8', errors='replace')[:200]}]")
                        return

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        try:
                            obj = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        candidates = obj.get("candidates", [])
                        if not candidates:
                            continue

                        cand = candidates[0]
                        content_obj = cand.get("content", {})
                        parts = content_obj.get("parts", [])

                        for p in parts:
                            if "text" in p:
                                yield StreamChunk(delta_text=p["text"])
                            elif "functionCall" in p:
                                fc = p["functionCall"]
                                yield StreamChunk(
                                    tool_calls=[{
                                        "id": f"gemini_{fc.get('name')}",
                                        "name": fc.get("name"),
                                        "arguments": json.dumps(fc.get("args", {}))
                                    }],
                                    finish_reason="tool_calls"
                                )
        except Exception as e:
            logger.error(f"Gemini streaming error: {e}")
            yield StreamChunk(delta_text=f"\n[Gemini stream error: {str(e)}]")
