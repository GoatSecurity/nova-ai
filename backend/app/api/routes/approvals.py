from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from backend.app.database.repositories.execution_repo import ExecutionRepository
from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.core.events import event_bus, AgentEvent

router = APIRouter(prefix="/approvals", tags=["Approvals & Permissions"])

class ApprovalDecisionRequest(BaseModel):
    decision: str  # "approved_once", "approved_session", "denied"
    actor: Optional[str] = "user"

@router.get("/{approval_id}")
async def get_approval(approval_id: str):
    app = await ExecutionRepository.get_approval(approval_id)
    if not app:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return app

@router.post("/{approval_id}/decide")
async def decide_approval(approval_id: str, req: ApprovalDecisionRequest, bg_tasks: BackgroundTasks):
    app = await ExecutionRepository.get_approval(approval_id)
    if not app:
        raise HTTPException(status_code=404, detail="Approval request not found")

    decided = await ExecutionRepository.decide_approval(
        approval_id=approval_id,
        decision=req.decision,
        actor=req.actor or "user"
    )

    conv_id = app["conversation_id"]

    # If approved for session, create session permission grant
    if req.decision == "approved_session":
        await ExecutionRepository.create_session_permission(
            conversation_id=conv_id,
            scope="all_safe",
            cwd=app["cwd"]
        )

    # Broadcast decision to UI
    await event_bus.publish(AgentEvent(
        event_type="status",
        conversation_id=conv_id,
        data={"status": "approval_decided", "decision": req.decision, "approval_id": approval_id}
    ))

    # Resume the agent loop cleanly on both approval and denial so the turn finishes properly
    if req.decision in ("approved_once", "approved_session", "denied"):
        bg_tasks.add_task(AgentOrchestrator.run_turn, conv_id, "", approval_id)

    return {"status": "decided", "approval": decided}
