from typing import Dict, Any, Optional
from backend.app.providers.base import BaseProviderAdapter
from backend.app.providers.openai_compatible import OpenAICompatibleAdapter
from backend.app.providers.anthropic import AnthropicAdapter
from backend.app.providers.gemini import GeminiAdapter
from backend.app.providers.ollama import OllamaAdapter
from backend.app.providers.local_inference import LocalInferenceAdapter
from backend.app.database.repositories.provider_repo import ProviderRepository

class ProviderRegistry:
    @staticmethod
    def create_adapter(provider_data: Dict[str, Any]) -> BaseProviderAdapter:
        ptype = provider_data.get("provider_type", "openai_compatible")
        prov_id = provider_data["id"]
        name = provider_data["name"]
        base_url = provider_data["base_url"]
        api_key = provider_data.get("api_key_decrypted") or ""
        custom_headers = provider_data.get("custom_headers") or {}
        models_endpoint = provider_data.get("models_endpoint") or "/models"
        chat_endpoint = provider_data.get("chat_endpoint") or "/chat/completions"

        if ptype == "ollama":
            return OllamaAdapter(
                provider_id=prov_id,
                name=name,
                base_url=base_url,
                api_key=api_key,
                custom_headers=custom_headers,
                models_endpoint=models_endpoint or "/api/tags",
                chat_endpoint=chat_endpoint or "/api/chat"
            )
        elif ptype == "anthropic":
            return AnthropicAdapter(
                provider_id=prov_id,
                name=name,
                base_url=base_url,
                api_key=api_key,
                custom_headers=custom_headers,
                models_endpoint=models_endpoint,
                chat_endpoint=chat_endpoint
            )
        elif ptype == "gemini":
            return GeminiAdapter(
                provider_id=prov_id,
                name=name,
                base_url=base_url,
                api_key=api_key,
                custom_headers=custom_headers,
                models_endpoint=models_endpoint,
                chat_endpoint=chat_endpoint
            )
        elif ptype == "lm_studio":
            return LocalInferenceAdapter(
                provider_id=prov_id,
                name=name,
                base_url=base_url,
                api_key=api_key,
                custom_headers=custom_headers,
                models_endpoint=models_endpoint,
                chat_endpoint=chat_endpoint
            )
        else:
            return OpenAICompatibleAdapter(
                provider_id=prov_id,
                name=name,
                base_url=base_url,
                api_key=api_key,
                custom_headers=custom_headers,
                models_endpoint=models_endpoint,
                chat_endpoint=chat_endpoint
            )

    @staticmethod
    async def get_adapter_for_provider(provider_id: str) -> Optional[BaseProviderAdapter]:
        prov = await ProviderRepository.get_provider(provider_id, include_decrypted_key=True)
        if not prov:
            return None
        return ProviderRegistry.create_adapter(prov)

    @classmethod
    async def get_adapter(cls, provider_id: str) -> Optional[BaseProviderAdapter]:
        return await cls.get_adapter_for_provider(provider_id)
