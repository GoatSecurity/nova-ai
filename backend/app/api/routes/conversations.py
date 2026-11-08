from typing import Dict, Any, Optional
import re
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from backend.app.database.repositories.conversation_repo import ConversationRepository
from backend.app.database.repositories.execution_repo import ExecutionRepository
from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.core.events import event_bus, AgentEvent

router = APIRouter(prefix="/conversations", tags=["Conversations"])

def generate_smart_title(content: str) -> str:
    if not content:
        return "Session"
    clean = content.strip()
    # Strip slash commands if any, e.g. /research or /web
    clean = re.sub(r"^/[a-zA-Z0-9_-]+\s*", "", clean)
    # Strip markdown headers or list markers
    clean = re.sub(r"^[#*`\-\s]+", "", clean)
    
    # Strip conversational openers
    prefixes = [
        "please", "could you", "can you", "i want to", "help me with", "how to", "show me", "check"
    ]
    for p in prefixes:
        if clean.lower().startswith(p):
            clean = clean[len(p):].lstrip(" :,!-")
            
    # Check for URL queries
    url_match = re.search(r"https?://(?:www\.)?([^/\s]+)", clean)
    if url_match:
        domain = url_match.group(1)
        if "ip" in clean.lower():
            return f"IP Lookup ({domain})"
        return f"Web Query ({domain})"
        
    # Check for common shell commands
    cmd_match = re.search(r"\b(curl|ping|whoami|dir|ls|cat|git|pip|python|node|docker)\b", clean, re.IGNORECASE)
    if cmd_match:
        cmd = cmd_match.group(1).lower()
        if "whoami" in cmd:
            return "System Identity (whoami)"
        if "curl" in cmd:
            return "Network Request (curl)"
        return f"Terminal Command ({cmd})"

    first_line = clean.split("\n")[0].strip()
    if len(first_line) > 36:
        words = first_line[:36].split()
        if len(words) > 1:
            first_line = " ".join(words[:-1])
        else:
            first_line = first_line[:36]
    title = first_line.strip()
    return title if title else "New Session"


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Session"
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    agent_profile_id: Optional[str] = None
    system_prompt_id: Optional[str] = None
    workspace_path: Optional[str] = None
    permission_mode: Optional[str] = "allow_safe"

class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    agent_profile_id: Optional[str] = None
    system_prompt_id: Optional[str] = None
    workspace_path: Optional[str] = None
    permission_mode: Optional[str] = None
    is_pinned: Optional[int] = None
    is_archived: Optional[int] = None

class SendMessageRequest(BaseModel):
    content: str
    pre_approved_id: Optional[str] = None
    enable_thinking: Optional[bool] = None
    enable_search: Optional[bool] = None

class EditMessageRequest(BaseModel):
    content: str
    resend: bool = False
    enable_thinking: Optional[bool] = None
    enable_search: Optional[bool] = None

@router.get("")
async def list_conversations(include_archived: bool = False):
    return await ConversationRepository.list_conversations(include_archived=include_archived)

@router.post("")
async def create_conversation(req: CreateConversationRequest):
    return await ConversationRepository.create_conversation(
        title=req.title or "New Session",
        provider_id=req.provider_id,
        model_id=req.model_id,
        agent_profile_id=req.agent_profile_id,
        system_prompt_id=req.system_prompt_id,
        workspace_path=req.workspace_path,
        permission_mode=req.permission_mode or "allow_safe"
    )

@router.get("/{conv_id}")
async def get_conversation(conv_id: str):
    conv = await ConversationRepository.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await ConversationRepository.get_messages(conv_id, limit=200)
    tool_calls = await ExecutionRepository.list_conversation_tool_calls(conv_id)
    pending_approvals = await ExecutionRepository.list_pending_approvals(conv_id)
    is_running = AgentOrchestrator.is_turn_active(conv_id) and not bool(pending_approvals)
    return {
        "conversation": conv,
        "messages": messages,
        "tool_calls": tool_calls,
        "pending_approvals": pending_approvals,
        "is_running": is_running
    }

@router.patch("")
@router.patch("/")
async def update_active_or_first_conversation(req: Dict[str, Any]):
    conv_id = req.get("conversation_id")
    if not conv_id:
        convs = await ConversationRepository.list_conversations(include_archived=False)
        if convs:
            conv_id = convs[0]["id"]
    if conv_id:
        updates = {k: v for k, v in req.items() if k != "conversation_id" and v is not None}
        conv = await ConversationRepository.update_conversation(conv_id, updates)
        return conv or {"status": "ok", "id": conv_id}
    return {"status": "ok", "message": "No active conversation to update"}

@router.patch("/{conv_id}")
async def update_conversation(conv_id: str, req: UpdateConversationRequest):
    updates = req.model_dump(exclude_unset=True)
    conv = await ConversationRepository.update_conversation(conv_id, updates)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str):
    deleted = await ConversationRepository.delete_conversation(conv_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted", "id": conv_id}

@router.post("/{conv_id}/messages")
async def send_message(conv_id: str, req: SendMessageRequest, bg_tasks: BackgroundTasks):
    conv = await ConversationRepository.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Title generation is handled 100% autonomously by the AI model in AgentOrchestrator.run_turn
    # Launch agent orchestrator in background task so API responds immediately and streams via WS/SSE
    bg_tasks.add_task(AgentOrchestrator.run_turn, conv_id, req.content, req.pre_approved_id, req.enable_thinking, req.enable_search)
    return {"status": "queued", "conversation_id": conv_id}

@router.patch("/{conv_id}/messages/{message_id}")
async def edit_message(conv_id: str, message_id: str, req: EditMessageRequest, bg_tasks: BackgroundTasks):
    conv = await ConversationRepository.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    updated = await ConversationRepository.update_message(message_id, req.content)
    if not updated:
        raise HTTPException(status_code=404, detail="Message not found")

    if req.resend:
        # Cancel any active turn first
        AgentOrchestrator.cancel_turn(conv_id)
        # Delete subsequent turns so conversation history is rewound cleanly
        await ConversationRepository.delete_messages_after(conv_id, message_id)
        # Re-trigger turn with None prompt since message is already updated in DB
        bg_tasks.add_task(AgentOrchestrator.run_turn, conv_id, None, None, req.enable_thinking, req.enable_search)
        return {"status": "resubmitted", "message": updated}

    return {"status": "updated", "message": updated}

@router.post("/{conv_id}/cancel")
async def cancel_conversation_turn(conv_id: str):
    AgentOrchestrator.cancel_turn(conv_id)
    from backend.app.database.connection import get_db
    async with get_db() as db:
        await db.execute(
            "UPDATE execution_approvals SET status = 'denied', decided_at = CURRENT_TIMESTAMP WHERE conversation_id = ? AND status = 'pending';",
            (conv_id,)
        )
        await db.execute(
            "UPDATE tool_calls SET status = 'cancelled' WHERE conversation_id = ? AND status = 'waiting_approval';",
            (conv_id,)
        )
        await db.commit()
    await event_bus.publish(AgentEvent(
        event_type="done",
        conversation_id=conv_id,
        data={"cancelled": True}
    ))
    return {"status": "cancelled", "conversation_id": conv_id}

@router.post("/{conv_id}/retry")
async def retry_last_turn(conv_id: str, bg_tasks: BackgroundTasks):
    conv = await ConversationRepository.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    last_user = await ConversationRepository.get_last_user_message(conv_id)
    if not last_user:
        raise HTTPException(status_code=400, detail="No user message found to retry")

    AgentOrchestrator.cancel_turn(conv_id)
    await ConversationRepository.delete_messages_after(conv_id, last_user["id"])
    bg_tasks.add_task(AgentOrchestrator.run_turn, conv_id, None, None)
    return {"status": "retrying", "conversation_id": conv_id}
