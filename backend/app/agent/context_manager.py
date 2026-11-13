from typing import List, Dict, Any, Tuple
from backend.app.core.config import settings

class ContextManager:
    @staticmethod
    def estimate_tokens(content: Any) -> int:
        if not content:
            return 0
        if isinstance(content, str):
            # Roughly 1 token ~= 4 characters for English / code
            return max(1, len(content) // 4)
        if isinstance(content, list):
            total = 0
            for part in content:
                if isinstance(part, dict):
                    p_type = part.get("type")
                    if p_type == "text":
                        total += max(1, len(part.get("text", "")) // 4)
                    elif p_type == "image_url":
                        total += 1200
                    else:
                        total += max(1, len(str(part)) // 4)
                elif isinstance(part, str):
                    total += max(1, len(part) // 4)
            return max(1, total)
        return max(1, len(str(content)) // 4)

    @staticmethod
    def calculate_conversation_tokens(messages: List[Dict[str, Any]]) -> int:
        total = 0
        for m in messages:
            content = m.get("content", "")
            thoughts = m.get("thoughts", "")
            total += ContextManager.estimate_tokens(content)
            if thoughts:
                total += ContextManager.estimate_tokens(thoughts)
        return total

    @staticmethod
    def prune_context(
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_context_tokens: int = settings.MAX_CONTEXT_TOKENS,
        reserve_response_tokens: int = settings.RESERVE_TOKENS_FOR_RESPONSE
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Ensures the assembled messages stay within the target model context limit.
        Preserves system prompt and latest messages, truncating oldest middle messages.
        """
        budget = max_context_tokens - reserve_response_tokens
        sys_tokens = ContextManager.estimate_tokens(system_prompt)
        available = max(1000, budget - sys_tokens)

        # Preserve leading system prompt separately so it is never pruned away or double-counted
        leading_system = None
        history_msgs = list(messages)
        if history_msgs and history_msgs[0].get("role") == "system":
            leading_system = dict(history_msgs[0])
            history_msgs = history_msgs[1:]

        # Work backwards from the most recent non-system messages
        pruned: List[Dict[str, Any]] = []
        current_tokens = 0

        for msg in reversed(history_msgs):
            msg_tokens = ContextManager.estimate_tokens(msg.get("content", ""))
            if current_tokens + msg_tokens > available and len(pruned) >= 2:
                # Truncate older context
                break
            pruned.insert(0, dict(msg))
            current_tokens += msg_tokens

        if leading_system is not None:
            pruned.insert(0, leading_system)

        # Clean messages for LLM compatibility:
        # 1. Cap single message length to prevent 413 Payload Too Large, 408 Request Timeout, or context exhaustion
        # 2. Never send empty content for assistant messages (avoids 400 Bad Request on Copilot/OpenAI)
        # 3. Convert mid-conversation system feedback to user role for universal provider support
        MAX_SINGLE_MSG_CHARS = 16000
        for i, m in enumerate(pruned):
            if i == 0 and m.get("role") == "system":
                continue
            content = m.get("content")
            if isinstance(content, str):
                if len(content) > MAX_SINGLE_MSG_CHARS:
                    half = MAX_SINGLE_MSG_CHARS // 2
                    omitted = len(content) - MAX_SINGLE_MSG_CHARS
                    m["content"] = content[:half] + f"\n\n... [Content truncated: {omitted} characters omitted to preserve token budget] ...\n\n" + content[-half:]
                    content = m["content"]
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        txt = part.get("text", "")
                        if len(txt) > MAX_SINGLE_MSG_CHARS:
                            half = MAX_SINGLE_MSG_CHARS // 2
                            omitted = len(txt) - MAX_SINGLE_MSG_CHARS
                            part["text"] = txt[:half] + f"\n\n... [Content truncated: {omitted} characters omitted to preserve token budget] ...\n\n" + txt[-half:]

            if m.get("role") == "assistant":
                if isinstance(content, str) and not content.strip():
                    m["content"] = "[Tool call requested]"
                elif isinstance(content, list) and not content:
                    m["content"] = "[Tool call requested]"
            elif m.get("role") == "system" and i > 0:
                # Middle system message -> user role
                m["role"] = "user"

        # Universal Provider Compatibility (Gemini / Anthropic / OpenAI rule):
        # The conversation request must not end with an assistant message.
        if pruned and pruned[-1].get("role") == "assistant":
            pruned.append({
                "role": "user",
                "content": "Please review the tool execution output above and answer the user's request thoroughly."
            })

        stats = {
            "system_tokens": sys_tokens,
            "messages_tokens": current_tokens,
            "total_estimated_tokens": sys_tokens + current_tokens,
            "max_context_tokens": max_context_tokens,
            "remaining_budget": max(0, budget - (sys_tokens + current_tokens)),
            "pruned_count": len(messages) - len(pruned)
        }
        return pruned, stats
