import pytest
import asyncio
from backend.app.database.schema import init_db
from backend.app.database.repositories.conversation_repo import ConversationRepository
from backend.app.database.repositories.memory_repo import MemoryRepository
from backend.app.database.repositories.provider_repo import ProviderRepository
from backend.app.database.repositories.prompt_repo import PromptRepository

@pytest.mark.asyncio
async def test_database_initialization_and_seeding():
    await init_db()
    profiles = await PromptRepository.list_agent_profiles()
    assert len(profiles) >= 5, "Builtin agent profiles should be seeded"
    
    prompt = await PromptRepository.get_active_global_prompt()
    assert prompt is not None, "Default global prompt should exist"
    
    providers = await ProviderRepository.list_providers()
    assert len(providers) >= 0, 'Provider list should be queryable'

    from backend.app.agent.prompt_engine import PromptEngine
    facts = await MemoryRepository.list_facts(category="environment")
    assert not any("HTML <img> tags with direct URLs" in f["content"] for f in facts)
    sp = await PromptEngine.build_system_prompt()
    assert "Rich HTML/CSS Presentation & Inline Image Styling in Chat" in sp

@pytest.mark.asyncio
async def test_conversation_lifecycle():
    conv = await ConversationRepository.create_conversation(
        title="Test Diagnostics Session",
        permission_mode="allow_safe"
    )
    assert conv["id"] is not None
    assert conv["title"] == "Test Diagnostics Session"

    # Add messages
    m1 = await ConversationRepository.add_message(
        conversation_id=conv["id"],
        role="user",
        content="Please check system CPU and memory."
    )
    assert m1["id"] is not None

    m2 = await ConversationRepository.add_message(
        conversation_id=conv["id"],
        role="assistant",
        content="Inspecting system resources..."
    )
    assert m2["role"] == "assistant"

    messages = await ConversationRepository.get_messages(conv["id"])
    assert len(messages) == 2

    # Update conversation
    updated = await ConversationRepository.update_conversation(conv["id"], {"title": "Updated Title", "is_pinned": 1})
    assert updated["title"] == "Updated Title"
    assert updated["is_pinned"] == 1

    # Cleanup
    deleted = await ConversationRepository.delete_conversation(conv["id"])
    assert deleted is True

@pytest.mark.asyncio
async def test_memory_and_fts5_search():
    conv = await ConversationRepository.create_conversation(title="FTS Test")
    await ConversationRepository.add_message(
        conversation_id=conv["id"],
        role="user",
        content="QuantumSuperSecretTokenKeyword"
    )

    # Search via FTS5
    results = await MemoryRepository.search_messages_fts("QuantumSuperSecretTokenKeyword")
    assert len(results) > 0, "FTS5 should instantly find message by keyword"
    assert "QuantumSuperSecretTokenKeyword" in results[0]["content"]

    # Memory facts
    fact = await MemoryRepository.save_fact(
        conversation_id=conv["id"],
        category="project_detail",
        content="Project uses Python 3.11 with FastAPI and SQLite"
    )
    assert fact["id"] is not None

    facts = await MemoryRepository.search_facts("FastAPI")
    assert len(facts) >= 1
    assert "FastAPI" in facts[0]["content"]

    # Delete fact
    del_ok = await MemoryRepository.delete_fact(fact["id"])
    assert del_ok is True

    await ConversationRepository.delete_conversation(conv["id"])
