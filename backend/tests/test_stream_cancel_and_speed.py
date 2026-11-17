import pytest
import asyncio
from backend.app.providers.base import BaseProviderAdapter, ProviderCapabilities, StreamChunk
from backend.app.agent.orchestrator import _needs_tools, _needs_desktop_instructions, AgentOrchestrator

def test_needs_tools_routing():
    # Conversational, coding, questions, greetings -> False (0 tool schema overhead)
    assert _needs_tools("سلام") is False
    assert _needs_tools("\u0633\u0644\u0627\u0645 \u0686\u0637\u0648\u0631\u06cc\u061f") is False
    assert _needs_tools("\u062a\u0641\u0627\u0648\u062a \u0628\u06cc\u0646 \u0644\u06cc\u0633\u062a \u0648 \u062a\u0627\u067e\u0644 \u0686\u06cc\u0633\u062a\u061f") is False
    assert _needs_tools("Write a python function to compute fibonacci numbers") is False
    assert _needs_tools("Explain quantum computing in simple terms") is False
    assert _needs_tools("2 + 2 * 10") is False

    # Actual actions -> True
    assert _needs_tools("\u0628\u0627 \u0645\u0648\u0633 \u0648 \u06a9\u06cc\u0628\u0631\u062f \u0628\u0631\u0648 \u062a\u0648\u06cc \u06af\u0648\u06af\u0644 \u0633\u0631\u0686 \u06a9\u0646") is True
    assert _needs_tools("\u062f\u0631 \u0645\u0648\u0631\u062f \u0627\u062e\u0628\u0627\u0631 \u062a\u06a9\u0646\u0648\u0644\u0648\u0698\u06cc \u0633\u0631\u0686 \u06a9\u0646") is True
    assert _needs_tools("\u062a\u0648\u06cc \u062a\u0631\u0645\u06cc\u0646\u0627\u0644 \u062f\u0633\u062a\u0648\u0631 dir \u0631\u0648 \u0628\u0632\u0646") is True
    assert _needs_tools("\u0641\u0627\u06cc\u0644 config.json \u0631\u0648 \u0628\u062e\u0648\u0646") is True

    # Iteration > 0 always preserves tools
    assert _needs_tools("سلام", iteration=1) is True
    # Skills always preserve tools
    assert _needs_tools("سلام", skill_cmd="/rss") is True

def test_needs_desktop_instructions():
    assert _needs_desktop_instructions("Hello world") is False
    assert _needs_desktop_instructions("Calculate 10+20") is False
    assert _needs_desktop_instructions("\u0628\u0627 \u0645\u0648\u0633 \u06a9\u0644\u06cc\u06a9 \u06a9\u0646") is True
    assert _needs_desktop_instructions("\u0645\u0631\u0648\u0631\u06af\u0631 \u0631\u0648 \u0628\u0627\u0632 \u06a9\u0646") is True
    assert _needs_desktop_instructions("Click the submit button") is True

@pytest.mark.asyncio
async def test_stream_abort_and_cancellation():
    class DummyAdapter(BaseProviderAdapter):
        def get_capabilities(self):
            return ProviderCapabilities()
        async def test_connection(self):
            return True, "ok", {}
        async def discover_models(self):
            return []
        async def chat_stream(self, model, messages, tools=None, temperature=0.7, max_tokens=None, enable_thinking=None, conversation_id=None):
            yield StreamChunk(delta_text="chunk")

    adapter = DummyAdapter("test", "Test", "http://localhost:11434")

    # Mock response
    class MockResp:
        def __init__(self):
            self.closed = False
            self.is_closed = False
        async def aclose(self):
            self.closed = True
            self.is_closed = True

    resp = MockResp()
    adapter.register_active_stream("conv_123", None, resp)
    assert "conv_123" in adapter._active_streams

    # Test abort_stream
    aborted = await adapter.abort_stream("conv_123")
    assert aborted is True
    assert resp.closed is True
    assert "conv_123" not in adapter._active_streams

    # Test AgentOrchestrator abort
    AgentOrchestrator._active_adapters["conv_456"] = adapter
    resp2 = MockResp()
    adapter.register_active_stream("conv_456", None, resp2)

    await AgentOrchestrator.abort_turn_stream("conv_456")
    assert resp2.closed is True
    assert "conv_456" in AgentOrchestrator._cancelled_convs
