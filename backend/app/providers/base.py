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
        self._shared_client: Optional[httpx.AsyncClient] = None
        self._active_streams: Dict[str, Tuple[Optional[httpx.AsyncClient], Optional[httpx.Response]]] = {}

    def is_local_url(self) -> bool:
        return "127.0.0.1" in self.base_url or "localhost" in self.base_url or "::1" in self.base_url

    def get_client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        t = float(timeout or self.timeout_seconds)
        # 30s connect, max(t, 120s) read for deep model prefill/reasoning, 60s write
        to = httpx.Timeout(read=max(t, 120.0), connect=30.0, write=60.0, pool=60.0)
        # Local services (Ollama, LM Studio) connect directly; remote services use environment proxy
        trust_env = not self.is_local_url()
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=300.0)
        return httpx.AsyncClient(timeout=to, trust_env=trust_env, limits=limits)

    def get_shared_client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        """Returns a persistent pooled AsyncClient for fast keep-alive reuse without TLS renegotiation overhead."""
        if self._shared_client is None or self._shared_client.is_closed:
            t = float(timeout or self.timeout_seconds)
            to = httpx.Timeout(read=max(t, 120.0), connect=30.0, write=60.0, pool=60.0)
            trust_env = not self.is_local_url()
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=300.0)
            self._shared_client = httpx.AsyncClient(timeout=to, trust_env=trust_env, limits=limits)
        return self._shared_client

    def register_active_stream(
        self,
        conversation_id: Optional[str],
        client: Optional[httpx.AsyncClient],
        response: Optional[httpx.Response]
    ) -> None:
        if conversation_id:
            self._active_streams[conversation_id] = (client, response)

    def unregister_active_stream(self, conversation_id: Optional[str]) -> None:
        if conversation_id and conversation_id in self._active_streams:
            self._active_streams.pop(conversation_id, None)

    async def abort_stream(self, conversation_id: str) -> bool:
        """
        Immediately closes the active HTTP streaming response socket and transport,
        forcing the remote model provider server to receive a connection drop/reset
        and halt inference immediately.
        """
        if not conversation_id or conversation_id not in self._active_streams:
            return False
        client, response = self._active_streams.pop(conversation_id, (None, None))
        aborted = False
        try:
            if response is not None and not response.is_closed:
                await response.aclose()
                aborted = True
        except Exception:
            pass
        return aborted

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
        enable_thinking: Optional[bool] = None,
        conversation_id: Optional[str] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """Streams response tokens and tool calls from the model."""
        pass
