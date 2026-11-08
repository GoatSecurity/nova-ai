from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.database.repositories.memory_repo import MemoryRepository

router = APIRouter(prefix="/memory", tags=["Memory"])

class CreateFactRequest(BaseModel):
    category: str = "project_detail"
    content: str
    confidence: float = 1.0
    conversation_id: Optional[str] = None

@router.get("/facts")
async def list_facts(category: Optional[str] = None):
    return await MemoryRepository.list_facts(category)

@router.post("/facts")
async def create_fact(req: CreateFactRequest):
    return await MemoryRepository.save_fact(
        conversation_id=req.conversation_id,
        category=req.category,
        content=req.content,
        confidence=req.confidence
    )

@router.delete("/facts/{fact_id}")
async def delete_fact(fact_id: str):
    deleted = await MemoryRepository.delete_fact(fact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"status": "deleted", "id": fact_id}

@router.get("/search")
async def search_memory_and_messages(query: str):
    if not query:
        return {"facts": [], "messages": []}
    facts = await MemoryRepository.search_facts(query)
    messages = await MemoryRepository.search_messages_fts(query)
    return {"query": query, "facts": facts, "messages": messages}
