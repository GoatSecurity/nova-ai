import abc
import httpx
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
from pydantic import BaseModel, Field

class StreamChunk(BaseModel):
    delta_text: str = ""
    delta_thought: str = ""
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    finish_reason: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0

class ProviderCapabilities(BaseModel):
    model_discovery: bool = True
    streaming: bool = True
    function_calling: bool = True
    vision: bool = False
    reasoning: bool = False
    structured_output: bool = True
    local: bool = False

class BaseProviderAdapter(abc.ABC):
    def __init__(
        self,
        provider_id: str,
        name: str,
        base_url: str,
        api_key: str = "",
        custom_headers: Optional[Dict[str, str]] = None,
        models_endpoint: str = "/models",
        chat_endpoint: str = "/chat/completions",
        timeout_seconds: int = 60
    ):
        self.provider_id = provider_id
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.custom_headers = custom_headers or {}
        self.models_endpoint = models_endpoint
        self.chat_endpoint = chat_endpoint
        self.timeout_seconds = timeout_seconds

    def is_local_url(self) -> bool:
        return "127.0.0.1" in self.base_url or "localhost" in self.base_url or "::1" in self.base_url

    def get_client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        t = float(timeout or self.timeout_seconds)
        # 60s connect to tolerate proxy SSL handshakes; deep 600s read for long model reasoning; 120s write for large payloads
        to = httpx.Timeout(read=max(t, 600.0), connect=60.0, write=120.0, pool=120.0)
        # Local services (Ollama, LM Studio) connect directly; remote services use environment proxy
        trust_env = not self.is_local_url()
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=300.0)
        return httpx.AsyncClient(timeout=to, trust_env=trust_env, limits=limits)

    @abc.abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        pass

    @abc.abstractmethod
    async def test_connection(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Tests connectivity and returns (success, message, metadata)."""
        pass

    @abc.abstractmethod
    async def discover_models(self) -> List[Dict[str, Any]]:
        """Discovers and normalizes available models from the provider."""
        pass

    @abc.abstractmethod
    async def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        enable_thinking: Optional[bool] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """Streams response tokens and tool calls from the model."""
        pass
