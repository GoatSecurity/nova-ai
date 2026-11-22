import re
from typing import List, Dict, Any, Tuple, Optional
from backend.app.core.config import settings

class ContextManager:
    @staticmethod
    def estimate_tokens(content: Any) -> int:
        if not content:
            return 0
        if isinstance(content, str):
            # Roughly 1 token ~= 4 characters for English / code; slightly denser for Persian/Unicode
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
    def build_progress_ledger(messages: List[Dict[str, Any]], existing_summary: Optional[str] = None) -> str:
        """
        Builds a compact high-density Progress Ledger & State Summary.
        Keeps context lightweight (usually under 200-300 tokens) while preserving
        exact task objectives, verified technical findings, and immediate next steps.
        """
        if existing_summary and len(existing_summary.strip()) > 30:
            return existing_summary.strip()

        non_sys = [m for m in messages if m.get("role") != "system"]
        if not non_sys:
            return ""

        # 1. Primary task / goal from the first substantive user request
        goal = ""
        for m in non_sys:
            if m.get("role") == "user":
                c = str(m.get("content") or "").strip()
                if len(c) > 15:
                    lines = [l.strip() for l in c.splitlines() if l.strip()]
                    goal = " ".join(lines[:3])
                    if len(goal) > 280:
                        goal = goal[:277] + "..."
                    break

        # 2. Extract key file paths & artifacts mentioned
        all_text = " ".join(str(m.get("content") or "") for m in non_sys)
        paths = set(re.findall(r'[a-zA-Z]:\\[^\s"\'`<>]+|/[^\s"\'`<>]+(?:\.apk|\.so|\.py|\.dex|\.json|\.txt|\.xml)', all_text))
        relevant_paths = [p for p in paths if not p.startswith('/models') and not p.startswith('/v1') and len(p) > 5][:4]

        # 3. Extract confirmed facts and milestones from assistant turns
        findings = []
        for m in non_sys:
            if m.get("role") == "assistant":
                c = str(m.get("content") or "")
                pat_find = r"(?:\u062a\u0627\u06cc\u06cc\u062f \u0634\u062f\u0647|\u0645\u0634\u062e\u0635 \u0634\u062f|\u06cc\u0627\u0641\u062a \u0634\u062f|\u062a\u06a9\u0646\u0648\u0644\u0648\u0698\u06cc|\u0645\u0639\u0645\u0627\u0631\u06cc|Fingerprint|Framework|Architecture)[^\n]+"
                m_finds = re.findall(pat_find, c)
                for f in m_finds[:3]:
                    clean_f = f.strip('*# -')
                    if len(clean_f) > 8 and clean_f not in findings:
                        findings.append(clean_f[:120])

        # 4. Immediate next planned steps from the most recent assistant message
        next_steps = []
        for m in reversed(non_sys):
            if m.get("role") == "assistant":
                c = str(m.get("content") or "")
                if len(c) > 80:
                    pat_next = r"(?:\u0645\u0631\u062d\u0644\u0647|\u06af\u0627\u0645|\u0641\u0627\u0632|\u0639\u0645\u0644\u06cc\u0627\u062a \u0627\u062c\u0631\u0627\u06cc\u06cc|\u0627\u0642\u062f\u0627\u0645 \u0628\u0639\u062f\u06cc|Next steps?|Phase \d)[^\n]+"
                    m_steps = re.findall(pat_next, c, re.IGNORECASE)
                    for s in m_steps[:3]:
                        clean_s = s.strip('*# -')
                        if len(clean_s) > 8 and clean_s not in next_steps:
                            next_steps.append(clean_s[:120])
                    break

        ledger_lines = [
            "### \U0001f4cb CONVERSATION STATE & PROGRESS LEDGER (\u062e\u0644\u0627\u0635\u0647 \u0648\u0636\u0639\u06cc\u062a \u0648 \u067e\u06cc\u0634\u0631\u0641\u062a \u062a\u0627 \u0627\u06cc\u0646 \u0644\u062d\u0638\u0647):",
            f"- **Target Task / Goal (\u0647\u062f\u0641 \u0627\u0635\u0644\u06cc)**: {goal or 'Autonomous Analysis & Task Execution'}",
        ]
        if relevant_paths:
            ledger_lines.append(f"- **Key Target Files**: {', '.join(relevant_paths)}")
        if findings:
            ledger_lines.append("- **Completed Actions & Verified Results (\u062f\u0633\u062a\u0627\u0648\u0631\u062f\u0647\u0627 \u0648 \u0646\u062a\u0627\u06cc\u062c)**:")
            for f in findings[:4]:
                ledger_lines.append(f"  * {f}")
        if next_steps:
            ledger_lines.append("- **Immediate Next Planned Steps (\u0627\u0642\u062f\u0627\u0645\u0627\u062a \u0645\u0631\u062d\u0644\u0647 \u0628\u0639\u062f)**:")
            for ns in next_steps[:3]:
                ledger_lines.append(f"  * {ns}")

        return "\n".join(ledger_lines)

    @staticmethod
    def compact_conversation_history(
        messages: List[Dict[str, Any]],
        existing_summary: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Replaces older multi-turn monologue messages with a high-density Progress Ledger.
        Keeps context lightweight (<1,200 tokens total), eliminates context window exhaustion,
        and provides maximum clarity to the LLM.
        """
        non_sys = [m for m in messages if m.get("role") != "system"]
        total_chars = sum(len(str(m.get("content") or "")) for m in non_sys)
        if len(non_sys) <= 2 and total_chars < 3000:
            return messages, ""

        ledger_text = ContextManager.build_progress_ledger(messages, existing_summary)
        first_user = next((m for m in non_sys if m.get("role") == "user"), None)
        latest_user = next((m for m in reversed(non_sys) if m.get("role") == "user"), None)

        compacted: List[Dict[str, Any]] = []

        # 1. Preserve initial user goal/instructions (cap if extraordinarily long)
        if first_user and first_user != latest_user:
            c_user = str(first_user.get("content") or "")
            if len(c_user) > 600:
                c_user = c_user[:600] + "\n... [Remaining instructions preserved in Progress Ledger] ..."
            compacted.append({"role": "user", "content": c_user})

        # 2. Inject Progress Ledger as verified state
        compacted.append({
            "role": "user",
            "content": f"[SYSTEM LEDGER UPDATE]\n{ledger_text}"
        })
        compacted.append({
            "role": "assistant",
            "content": "Status acknowledged. Current progress and verified findings are recorded. Ready to execute the immediate next objective directly."
        })

        # 3. Latest user message with continuation directive if applicable
        if latest_user:
            user_text = str(latest_user.get("content") or "")
            continue_keywords = (
                "\u0627\u062f\u0627\u0645\u0647 \u0628\u062f\u0647",
                "\u062e\u0628 \u0627\u062f\u0627\u0645\u0647",
                "\u0628\u0631\u0648 \u062c\u0644\u0648",
                "\u0627\u0646\u062c\u0627\u0645 \u0628\u062f\u0647",
                "continue", "next", "proceed", "go ahead"
            )
            if any(kw in user_text.lower() for kw in continue_keywords):
                user_text += "\n\n[DIRECTIVE: The user commanded to proceed. Directly invoke the appropriate tool (such as run_python or execute_command) now for the next planned action. Do not output text monologues without tools.]"
            compacted.append({"role": "user", "content": user_text})

        return compacted, ledger_text

    @staticmethod
    def prune_context(
        system_prompt: str,
        messages: List[Dict[str, Any]],
        max_context_tokens: int = settings.MAX_CONTEXT_TOKENS,
        reserve_response_tokens: int = settings.RESERVE_TOKENS_FOR_RESPONSE,
        existing_summary: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Ensures the assembled messages stay within the target model context limit.
        Preserves system prompt and latest messages, truncating oldest middle messages.
        """
        # Step 1: Preserve leading system prompt separately so it is NEVER pruned away or displaced
        leading_system = None
        history_msgs = list(messages)
        if history_msgs and history_msgs[0].get("role") == "system":
            leading_system = dict(history_msgs[0])
            history_msgs = history_msgs[1:]
        elif system_prompt:
            leading_system = {"role": "system", "content": system_prompt}

        # Step 2: Intelligent Rolling Progress Summary Compaction
        # If conversation has multiple turns or history exceeds healthy token density,
        # compact verbose historical turns into an Active Progress Ledger.
        non_system_count = len(history_msgs)
        total_msg_tokens = ContextManager.calculate_conversation_tokens(history_msgs)

        compacted_ledger_text = ""
        if non_system_count > 2 or total_msg_tokens > 1200:
            compacted_msgs, compacted_ledger_text = ContextManager.compact_conversation_history(history_msgs, existing_summary)
            if compacted_msgs:
                history_msgs = compacted_msgs

        budget = max_context_tokens - reserve_response_tokens
        sys_tokens = ContextManager.estimate_tokens(leading_system.get("content", "") if leading_system else system_prompt)
        available = max(1000, budget - sys_tokens)

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

        # Multi-turn Vision Optimization: Keep only the most recent desktop screenshot in context.
        # Older screenshots are replaced with a lightweight text token so prompt prefill stays
        # under 2-3 seconds instead of timing out on self-hosted or remote model servers.
        latest_screenshot_kept = False
        for m in reversed(pruned):
            content = m.get("content")
            if isinstance(content, list):
                new_parts = []
                for part in reversed(content):
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        if not latest_screenshot_kept:
                            latest_screenshot_kept = True
                            new_parts.insert(0, part)
                        else:
                            new_parts.insert(0, {"type": "text", "text": "[Previous desktop frame cleared]"})
                    else:
                        new_parts.insert(0, part)
                m["content"] = new_parts

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
            "pruned_count": len(messages) - len(pruned),
            "compacted_ledger": compacted_ledger_text
        }
        return pruned, stats
