import pytest
import json
from backend.app.agent.tool_router import ToolRouter
from backend.app.providers.base import StreamChunk, ProviderCapabilities
from backend.app.providers.openai_compatible import OpenAICompatibleAdapter

def test_fallback_tool_calling_extractor():
    text_with_markdown = """
    Certainly! Let me inspect the project directory for you.

    ```json
    {
      "tool_call": {
        "name": "list_directory",
        "arguments": {
          "path": "C:\\my_project"
        }
      }
    }
    ```

    I will analyze the result once complete.
    """
    calls = ToolRouter.extract_fallback_tool_calls(text_with_markdown)
    assert len(calls) == 1
    assert calls[0]["name"] == "list_directory"
    args = json.loads(calls[0]["arguments"])
    assert args["path"] == "C:\\my_project"

def test_tool_argument_validation():
    # Valid call
    valid, err = ToolRouter.validate_tool_arguments(
        "calculate",
        {"expression": "2 + 2"}
    )
    assert valid is True

    # Missing required argument
    invalid, err = ToolRouter.validate_tool_arguments(
        "calculate",
        {}
    )
    assert invalid is False
    assert "Missing required parameter" in err

    # Cross-platform POSIX shells are valid
    valid_bash, _ = ToolRouter.validate_tool_arguments(
        "execute_command",
        {"command": "ls", "shell": "bash"}
    )
    assert valid_bash is True

    # Invalid enum value
    invalid_enum, err = ToolRouter.validate_tool_arguments(
        "execute_command",
        {"command": "dir", "shell": "unsupported_shell"}
    )
    assert invalid_enum is False
    assert "Must be one of" in err


@pytest.mark.asyncio
async def test_models_ordered_oldest_provider_to_newest():
    from backend.app.database.schema import init_db
    from backend.app.database.repositories.provider_repo import ProviderRepository

    await init_db()
    # Deliberately name first provider starting with Z and second with A to prove creation-order wins over alphabetical
    p_old = await ProviderRepository.create_provider(
        name="Zebra First Provider",
        provider_type="openai_compatible",
        base_url="http://127.0.0.1:9991/v1",
    )
    p_new = await ProviderRepository.create_provider(
        name="Alpha Second Provider",
        provider_type="openai_compatible",
        base_url="http://127.0.0.1:9992/v1",
    )
    try:
        await ProviderRepository.sync_models(p_old["id"], [{"model_name": "z-first-model", "is_local": False}])
        await ProviderRepository.sync_models(p_new["id"], [{"model_name": "a-second-model", "is_local": True}])

        all_models = await ProviderRepository.list_all_models()
        idx_old = next(i for i, m in enumerate(all_models) if m["provider_id"] == p_old["id"])
        idx_new = next(i for i, m in enumerate(all_models) if m["provider_id"] == p_new["id"])
        assert idx_old < idx_new, "Models from older provider must precede models from newer provider"
    finally:
        await ProviderRepository.delete_provider(p_old["id"])
        await ProviderRepository.delete_provider(p_new["id"])


@pytest.mark.asyncio
async def test_think_off_stripping_and_monologue_guards():
    from backend.app.agent.orchestrator import (
        _strip_internal_tags,
        _compute_safe_stream_views,
        _strip_leading_meta_monologue,
    )
    from backend.app.agent.prompt_engine import PromptEngine

    # 1. Dangling closing </think> (without opening <think>) must be stripped from visible text
    cleaned, thk = _strip_internal_tags("Internal thoughts\n</think>\n\nHello! I am doing great.")
    assert cleaned == "Hello! I am doing great."
    assert "Internal thoughts" in thk

    # 2. Leading English meta-monologue leaked before answer is cleanly separated
    reply, mono = _strip_leading_meta_monologue(
        'The user said "hi" which is a greeting. Let me give a friendly greeting.\n\nHello! Welcome.'
    )
    assert reply == "Hello! Welcome."
    assert "The user said" in mono

    # 3. Partial ambiguous line during streaming is held back cleanly before newline
    vis_partial, _ = _compute_safe_stream_views('The user asked "how are you"')
    assert vis_partial == ""

    vis_after, thk_after = _compute_safe_stream_views('The user asked "how are you"\n\nHello! Doing great.')
    assert vis_after == "Hello! Doing great."
    assert "The user asked" in thk_after

    # 4. System prompt clearly disables thinking when enable_thinking=False
    sp_no_think = await PromptEngine.build_system_prompt(enable_thinking=False)
    assert "THINKING OFF" in sp_no_think
