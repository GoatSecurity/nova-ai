import pytest
import re
from backend.app.database.repositories.conversation_repo import ConversationRepository
from backend.app.database.schema import init_db
from backend.app.agent.orchestrator import AgentOrchestrator

@pytest.mark.asyncio
async def test_attachment_persistence_and_parsing():
    await init_db()

    # 1. Create a test conversation
    conv = await ConversationRepository.create_conversation(
        title="Multimodal Test",
        permission_mode="allow_safe"
    )
    conv_id = conv["id"]

    # 2. Add message with text attachment
    text_payload = (
        '<attachment type="text" name="solution.py" mime="text/x-python" size="45">'
        'def add(a, b):\n    return a + b\n'
        '</attachment>\n\n'
        'Please review my math function.'
    )
    user_msg = await ConversationRepository.add_message(
        conversation_id=conv_id,
        role="user",
        content=text_payload
    )

    # 3. Retrieve messages and verify stored content
    messages = await ConversationRepository.get_messages(conv_id)
    assert len(messages) >= 1
    stored = messages[-1]["content"]
    assert '<attachment type="text" name="solution.py"' in stored
    assert 'def add(a, b):' in stored
    assert 'Please review my math function.' in stored

@pytest.mark.asyncio
async def test_image_attachment_handling():
    await init_db()

    conv = await ConversationRepository.create_conversation(
        title="Image Test",
        permission_mode="allow_safe"
    )
    conv_id = conv["id"]

    # Add message with image attachment
    image_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    img_payload = (
        f'<attachment type="image" name="screen.png" mime="image/png" size="100">'
        f'{image_b64}'
        f'</attachment>\n\n'
        f'What is in this screenshot?'
    )
    await ConversationRepository.add_message(
        conversation_id=conv_id,
        role="user",
        content=img_payload
    )

    messages = await ConversationRepository.get_messages(conv_id)
    stored = messages[-1]["content"]
    assert '<attachment type="image" name="screen.png"' in stored
    assert image_b64 in stored
