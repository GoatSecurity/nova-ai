from typing import List, Dict, Any, Optional
from fastapi import APIRouter
from backend.app.tools.registry import tool_registry

router = APIRouter(prefix="/tools", tags=["Tools"])

@router.get("")
async def list_tools():
    tools = tool_registry.list_tools()
    return [
        {
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "risk_level": t.risk_level,
            "requires_approval": t.requires_approval,
            "parameters": [p.model_dump() for p in t.parameters]
        }
        for t in tools
    ]
