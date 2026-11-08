from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from backend.app.database.repositories.execution_repo import ExecutionRepository
from backend.app.execution.process_manager import ProcessManager

router = APIRouter(prefix="/executions", tags=["Executions"])

@router.get("/conversations/{conv_id}")
async def list_conversation_executions(conv_id: str):
    return await ExecutionRepository.list_conversation_tool_calls(conv_id)

@router.post("/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    cancelled = await ProcessManager.cancel_execution(execution_id)
    return {"status": "cancelled" if cancelled else "not_found_or_finished", "id": execution_id}
