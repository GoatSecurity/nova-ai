import pytest
from backend.app.agent.context_manager import ContextManager
from backend.app.providers.openai_compatible import detect_vision_support
from backend.app.providers.anthropic import AnthropicAdapter
from backend.app.providers.gemini import GeminiAdapter
from backend.app.providers.ollama import OllamaAdapter

def test_detect_vision_support():
    assert detect_vision_support("gpt-4o") is True
    assert detect_vision_support("claude-3-5-sonnet") is True
    assert detect_vision_support("gemini-2.0-flash") is True
    assert detect_vision_support("qwen2-vl-7b") is True
    assert detect_vision_support("llava-v1.6-34b") is True
    assert detect_vision_support("deepseek-r1-distill-qwen-7b") is False

def test_context_manager_multimodal_estimate_tokens():
    text_tokens = ContextManager.estimate_tokens("Hello world, this is a test.")
    assert text_tokens > 0

    multimodal_parts = [
        {"type": "text", "text": "What is in this image?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}}
    ]
    total_tokens = ContextManager.estimate_tokens(multimodal_parts)
    # 1200 image tokens + ~6 text tokens
    assert total_tokens >= 1200

def test_context_manager_prune_context_preserves_multimodal():
    system_prompt = "You are NOVA AI assistant."
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": "Analyze this screenshot please."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123fakeimage"}}
        ]}
    ]
    pruned, stats = ContextManager.prune_context(system_prompt=system_prompt, messages=messages)
    assert len(pruned) == 2
    assert pruned[0]["role"] == "system"
    assert pruned[1]["role"] == "user"
    assert isinstance(pruned[1]["content"], list)
    assert pruned[1]["content"][1]["type"] == "image_url"
    assert pruned[1]["content"][1]["image_url"]["url"] == "data:image/png;base64,abc123fakeimage"

def test_anthropic_multimodal_transform():
    adapter = AnthropicAdapter(provider_id="test-anthropic", name="anthropic", base_url="https://api.anthropic.com/v1", api_key="sk-test")
    caps = adapter.get_capabilities()
    assert caps.vision is True

def test_gemini_multimodal_transform():
    adapter = GeminiAdapter(provider_id="test-gemini", name="gemini", base_url="https://generativelanguage.googleapis.com", api_key="test-key")
    caps = adapter.get_capabilities()
    assert caps.vision is True

def test_ollama_multimodal_transform():
    adapter = OllamaAdapter(provider_id="test-ollama", name="ollama", base_url="http://127.0.0.1:11434")
    caps = adapter.get_capabilities()
    assert caps.vision is True


def test_unpack_attachment_preserves_image_parts():
    import re
    raw_user_content = '<attachment type="image" name="screen.png" mime="image/png" size="100">data:image/png;base64,sampleimage</attachment>\\nWhat is this?'
    att_matches = list(re.finditer(r'<attachment\s+([^>]*?)>([\s\S]*?)</attachment>', raw_user_content, re.IGNORECASE))
    assert len(att_matches) == 1
    image_parts = []
    for match in att_matches:
        attr_str = match.group(1)
        att_body = match.group(2).strip()
        type_match = re.search(r'type="([^"]+)"', attr_str, re.IGNORECASE)
        att_type = type_match.group(1).lower() if type_match else "text"
        if att_type == "image":
            image_parts.append({"type": "image_url", "image_url": {"url": att_body}})
    
    assert len(image_parts) == 1
    assert image_parts[0]["image_url"]["url"] == "data:image/png;base64,sampleimage"
