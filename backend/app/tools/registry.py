from typing import Dict, Any, List, Optional, Callable, Awaitable
from backend.app.tools.base import BaseTool
from backend.app.core.logging import logger

ToolHandler = Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._handlers: Dict[str, ToolHandler] = {}

    def register(self, tool: BaseTool, handler: ToolHandler):
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler
        logger.debug(f"Registered tool: {tool.name} [{tool.category}]")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_handler(self, name: str) -> Optional[ToolHandler]:
        return self._handlers.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_openai_tools(self, filter_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        tools = []
        for name, tool in self._tools.items():
            if filter_names is None or name in filter_names:
                tools.append(tool.to_openai_schema())
        return tools

    async def execute_tool(self, name: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        handler = self._handlers.get(name)
        if not handler:
            return {"error": f"Tool '{name}' not found in registry."}
        try:
            return await handler(arguments, context)
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            return {"error": f"Tool execution failed: {str(e)}"}

tool_registry = ToolRegistry()
