import re
import json
import uuid
from typing import List, Dict, Any, Optional, Tuple
from backend.app.tools.registry import tool_registry
from backend.app.core.logging import logger

def _clean_json_str(s: str) -> str:
    # Fix unescaped single backslashes in Windows file paths for JSON parser
    # Replace backslashes not followed by valid JSON escape chars: ", \, /, b, f, n, r, t, u
    cleaned = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', s)
    return cleaned

class ToolRouter:
    @staticmethod
    def extract_fallback_tool_calls(text: str) -> List[Dict[str, Any]]:
        """
        Extracts structured tool calls from model generated text
        when the model does not support native tool calling.
        """
        tool_calls = []

        # Pattern 1: ```json { "tool_call": ... } ``` or ``` { "tool_call": ... } ```
        code_block_pattern = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
        for match in code_block_pattern.finditer(text):
            block_content = match.group(1).strip()
            if '"tool_call"' in block_content:
                try:
                    data = json.loads(block_content)
                except json.JSONDecodeError:
                    try:
                        data = json.loads(_clean_json_str(block_content))
                    except Exception:
                        continue

                tc = data.get("tool_call")
                if isinstance(tc, dict) and "name" in tc:
                    name = tc["name"]
                    args = tc.get("arguments", {})
                    tool_calls.append({
                        "id": f"fallback_{str(uuid.uuid4())[:8]}",
                        "name": name,
                        "arguments": json.dumps(args) if isinstance(args, dict) else str(args)
                    })

        # Pattern 2: inline JSON { "tool_call": { ... } } without code blocks
        if not tool_calls:
            inline_pattern = re.compile(r"\{\s*\"tool_call\"\s*:\s*\{.*?\}\s*\}", re.DOTALL)
            for match in inline_pattern.finditer(text):
                block_content = match.group(0).strip()
                try:
                    data = json.loads(block_content)
                except json.JSONDecodeError:
                    try:
                        data = json.loads(_clean_json_str(block_content))
                    except Exception:
                        continue

                tc = data.get("tool_call")
                if isinstance(tc, dict) and "name" in tc:
                    name = tc["name"]
                    args = tc.get("arguments", {})
                    tool_calls.append({
                        "id": f"fallback_{str(uuid.uuid4())[:8]}",
                        "name": name,
                        "arguments": json.dumps(args) if isinstance(args, dict) else str(args)
                    })

        return tool_calls

    @staticmethod
    def validate_tool_arguments(tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
        tool = tool_registry.get_tool(tool_name)
        if not tool:
            return False, f"Unknown tool '{tool_name}'."

        for param in tool.parameters:
            if param.required and param.name not in arguments:
                return False, f"Missing required parameter '{param.name}' for tool '{tool_name}'."
            if param.name in arguments and param.enum:
                val = arguments[param.name]
                if val not in param.enum:
                    return False, f"Invalid value '{val}' for parameter '{param.name}'. Must be one of: {param.enum}"

        return True, ""
