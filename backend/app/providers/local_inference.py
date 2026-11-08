from typing import Dict, Any, List
from backend.app.providers.openai_compatible import OpenAICompatibleAdapter
from backend.app.providers.base import ProviderCapabilities

class LocalInferenceAdapter(OpenAICompatibleAdapter):
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

    async def discover_models(self) -> List[Dict[str, Any]]:
        models = await super().discover_models()
        for m in models:
            m["is_local"] = True
        return models
