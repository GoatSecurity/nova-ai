from typing import Dict, Any, List, Optional, Callable, Awaitable
from pydantic import BaseModel, Field

class ToolParameter(BaseModel):
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[str]] = None

class BaseTool(BaseModel):
    name: str
    description: str
    parameters: List[ToolParameter]
    risk_level: str = "LOW"  # LOW, MODERATE, HIGH, CRITICAL
    requires_approval: bool = False
    category: str = "system"  # system, filesystem, development, utility

    def to_openai_schema(self) -> Dict[str, Any]:
        """Converts tool definition to OpenAI / JSON schema tool definition."""
        properties = {}
        required = []
        for p in self.parameters:
            prop = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            if p.default is not None:
                prop["default"] = p.default
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
