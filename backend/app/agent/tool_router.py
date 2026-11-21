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

def _find_balanced_json_objects(text: str) -> List[Tuple[int, int, str]]:
    """
    Finds all top-level balanced JSON objects in text.
    Correctly tracks quotes, escapes, and nested braces.
    Returns list of (start_index, end_index, json_str).
    """
    results = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '{':
            start = i
            depth = 0
            in_str = False
            esc = False
            valid = False
            for j in range(start, n):
                c = text[j]
                if esc:
                    esc = False
                    continue
                if c == '\\':
                    if in_str:
                        esc = True
                    continue
                if c == '"':
                    in_str = not in_str
                    continue
                if not in_str:
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            results.append((start, j + 1, text[start:j + 1]))
                            i = j + 1
                            valid = True
                            break
            if not valid:
                i += 1
        else:
            i += 1
    return results

def _safe_parse_json(s: str) -> Optional[Dict[str, Any]]:
    """Attempts to parse JSON with multiple robust fallback strategies."""
    # 1. Direct parse with strict=False (allows literal newlines/tabs inside strings)
    try:
        data = json.loads(s, strict=False)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 2. Fix unescaped Windows backslashes
    try:
        cleaned = _clean_json_str(s)
        data = json.loads(cleaned, strict=False)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 3. Fix trailing commas
    try:
        s_fix = re.sub(r",\s*([\]}])", r"\1", s)
        data = json.loads(s_fix, strict=False)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return None

class ToolRouter:
    @staticmethod
    def extract_fallback_tool_calls(text: str) -> List[Dict[str, Any]]:
        """
        Extracts structured tool calls from model generated text
        when the model does not support native tool calling.
        Uses balanced-brace scanning and supports multiple agent formats.
        """
        if not text:
            return []

        tool_calls = []
        registered_tools = set(tool_registry._tools.keys()) if hasattr(tool_registry, "_tools") else set()

        # 1. Check XML-style blocks first: <tool_call>...</tool_call> or <function_call>...</function_call>
        xml_pattern = re.compile(r"<(?:tool_call|function_call|tool|call)>([\s\S]*?)</(?:tool_call|function_call|tool|call)>", re.IGNORECASE)
        for match in xml_pattern.finditer(text):
            inner = match.group(1).strip()
            for _, _, obj_str in _find_balanced_json_objects(inner):
                data = _safe_parse_json(obj_str)
                if not data:
                    continue
                name, args = ToolRouter._extract_name_and_args(data, registered_tools)
                if name:
                    tool_calls.append({
                        "id": f"fallback_{str(uuid.uuid4())[:8]}",
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
                    })

        # 2. Check Markdown code blocks: ```json { ... } ``` or ``` { ... } ```
        code_block_pattern = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)
        for match in code_block_pattern.finditer(text):
            block_content = match.group(1).strip()
            for _, _, obj_str in _find_balanced_json_objects(block_content):
                data = _safe_parse_json(obj_str)
                if not data:
                    continue
                name, args = ToolRouter._extract_name_and_args(data, registered_tools)
                if name:
                    tool_calls.append({
                        "id": f"fallback_{str(uuid.uuid4())[:8]}",
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
                    })

        # 3. Direct balanced JSON objects anywhere in text
        if not tool_calls:
            for _, _, obj_str in _find_balanced_json_objects(text):
                data = _safe_parse_json(obj_str)
                if not data:
                    continue
                name, args = ToolRouter._extract_name_and_args(data, registered_tools)
                if name:
                    tool_calls.append({
                        "id": f"fallback_{str(uuid.uuid4())[:8]}",
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
                    })

        # 4. Truncated / interrupted tool block auto-repair
        if not tool_calls:
            m_unclosed = re.search(r'(?:```(?:json)?\s*)?(\{?\s*"(?:tool_call|function_call|action|name)"[\s\S]+)$', text, re.IGNORECASE)
            if m_unclosed:
                candidate = m_unclosed.group(1).rstrip()
                if not candidate.startswith('{'):
                    candidate = '{' + candidate
                for suffix in ['"}}', '"}}}', '\'\\n"}}', '\'\\n"}}}', '\\n"}}', '\\n"}}}', '}}}', '}}']:
                    repaired_data = _safe_parse_json(candidate + suffix)
                    if repaired_data:
                        name, args = ToolRouter._extract_name_and_args(repaired_data, registered_tools)
                        if name:
                            tool_calls.append({
                                "id": f"fallback_{str(uuid.uuid4())[:8]}",
                                "name": name,
                                "arguments": json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
                            })
                            logger.info(f"Successfully repaired and extracted interrupted tool call: {name}")
                            break

        return tool_calls

    @staticmethod
    def _extract_name_and_args(data: Dict[str, Any], registered_tools: set) -> Tuple[Optional[str], Any]:
        """Extracts tool name and arguments from various agent tool calling schemas."""
        name = None
        args = {}

        # Standard schema: {"tool_call": {"name": ..., "arguments": ...}}
        if "tool_call" in data and isinstance(data["tool_call"], dict):
            tc = data["tool_call"]
            name = tc.get("name")
            args = tc.get("arguments", tc.get("parameters", {}))
        # Direct schema: {"name": "<tool_name>", "arguments": ...}
        elif "name" in data:
            candidate = str(data["name"]).strip()
            if candidate in registered_tools or "arguments" in data or "parameters" in data or tool_registry.get_tool(candidate):
                name = candidate
                args = data.get("arguments", data.get("parameters", {}))
        # Action schema: {"action": "<tool_name>", "action_input": ...}
        elif "action" in data:
            candidate = str(data["action"]).strip()
            if candidate in registered_tools or "action_input" in data or "arguments" in data or tool_registry.get_tool(candidate):
                name = candidate
                args = data.get("action_input", data.get("arguments", {}))
        # Tool schema: {"tool": "<tool_name>", "args": ...}
        elif "tool" in data:
            candidate = str(data["tool"]).strip()
            if candidate in registered_tools or "args" in data or "arguments" in data or tool_registry.get_tool(candidate):
                name = candidate
                args = data.get("args", data.get("arguments", {}))

        return name, args

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
