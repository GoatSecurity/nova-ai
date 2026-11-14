import json

import uuid

import re

import asyncio

import time

from typing import Dict, Any, List, Optional, Tuple

from backend.app.core.events import event_bus, AgentEvent

from backend.app.core.config import settings

from backend.app.core.logging import logger, audit_log

from backend.app.database.connection import get_db

from backend.app.database.repositories.conversation_repo import ConversationRepository

from backend.app.database.repositories.provider_repo import ProviderRepository

from backend.app.database.repositories.execution_repo import ExecutionRepository

from backend.app.agent.prompt_engine import PromptEngine

from backend.app.agent.context_manager import ContextManager

from backend.app.agent.tool_router import ToolRouter

from backend.app.tools.registry import tool_registry

from backend.app.providers.registry import ProviderRegistry

from backend.app.providers.base import StreamChunk





_INTERNAL_TAGS = ("<think>", "</think>", "<session_title>", "</session_title>", "<title>", "</title>")

_TAG_SPLIT_RE = re.compile(r"<(/?(?:think|session_title|title))>", re.IGNORECASE)





def _strip_raw_tool_calls(text: str) -> str:
    """
    Strips raw tool invocation payloads (such as ```json {"tool_call": ...} ``` or
    {"tool_call": ...} or <tool_call>...</tool_call>) from model output so raw
    machine-level tool calls never leak into user chat messages.
    """
    if not text:
        return ""

    # 1. Stripping code blocks with tool_call or function_call or direct tool JSON
    cleaned = re.sub(
        r"```(?:json)?\s*\{\s*(?:\"tool_call\"|\"function_call\"|\"call\"|\"action\"|\"name\"\s*:)\s*[\s\S]*?\}\s*```",
        "",
        text,
        flags=re.IGNORECASE
    )

    # 2. Stripping XML style tags: <tool_call>...</tool_call>, <function_call>...</function_call>, <tool>...</tool>, <call>...</call>
    cleaned = re.sub(
        r"\s*<(?:tool_call|function_call|tool|call)>[\s\S]*?</(?:tool_call|function_call|tool|call)>\s*",
        "\n\n",
        cleaned,
        flags=re.IGNORECASE
    )

    # 3. Stripping standalone JSON objects with "tool_call" or "function_call"
    cleaned = re.sub(
        r"\{\s*\"(?:tool_call|function_call)\"\s*:\s*\{[\s\S]*?\}\s*\}",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    # Clean up excess whitespace / blank lines leftover from stripped blocks
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _strip_internal_tags(text: str) -> Tuple[str, str]:

    """Removes internal tags (<think>, <session_title>, <title>) and returns (clean_text, extracted_thoughts)."""

    if not text:

        return "", ""

    thoughts_parts: List[str] = []



    def _collect_think(m: re.Match) -> str:

        inner = m.group(1).strip()

        if inner:

            thoughts_parts.append(inner)

        return ""



    # Handle dangling leading </think> emitted by templates that pre-open <think> in prompt prefix

    if "</think>" in text.lower():

        first_close = text.lower().find("</think>")

        first_open = text.lower().find("<think>")

        if first_open == -1 or first_close < first_open:

            dangling_thought = text[:first_close].strip()

            if dangling_thought:

                thoughts_parts.append(dangling_thought)

            text = text[first_close + len("</think>"):]



    cleaned = re.sub(r"<think>([\s\S]*?)</think>", _collect_think, text, flags=re.IGNORECASE)

    unclosed = re.search(r"<think>([\s\S]*)$", cleaned, flags=re.IGNORECASE)

    if unclosed:

        inner = unclosed.group(1).strip()

        if inner:

            thoughts_parts.append(inner)

        cleaned = cleaned[:unclosed.start()]

    cleaned = re.sub(r"<(?:session_title|title)>[\s\S]*?</(?:session_title|title)>\s*", "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"<(?:session_title|title)>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip(), "\n".join(thoughts_parts).strip()





def _compute_safe_stream_views(raw_text: str) -> Tuple[str, str]:

    """

    Parses partially streamed raw_text safely into (visible_text_so_far, inline_think_text_so_far),

    holding back trailing partial internal tag prefixes.

    """

    safe_end = len(raw_text)

    last_lt = raw_text.rfind("<")

    if last_lt != -1 and ">" not in raw_text[last_lt:]:

        tail = raw_text[last_lt:].lower()

        if any(tag.startswith(tail) for tag in _INTERNAL_TAGS):

            safe_end = last_lt



    work = raw_text[:safe_end]

    # Handle implicit leading think block if an unmatched </think> appears first

    low_work = work.lower()

    if "</think>" in low_work:

        fc = low_work.find("</think>")

        fo = low_work.find("<think>")

        if fo == -1 or fc < fo:

            lead_thought = work[:fc]

            rest_work = work[fc + len("</think>"):]

            vis_tail, think_tail = _compute_safe_stream_views(rest_work)

            combined_think = (lead_thought + ("\n" if lead_thought and think_tail else "") + think_tail).strip()

            return vis_tail, combined_think



    vis_parts: List[str] = []

    think_parts: List[str] = []

    pos = 0

    state = "visible"

    for m in _TAG_SPLIT_RE.finditer(work):

        segment = work[pos:m.start()]

        if state == "visible":

            vis_parts.append(segment)

        elif state == "think":

            think_parts.append(segment)

        tag = m.group(1).lower()

        if tag == "think":

            state = "think"

        elif tag in ("session_title", "title"):

            state = "title"

        elif tag in ("/think", "/session_title", "/title"):

            state = "visible"

        pos = m.end()



    rem = work[pos:]

    if state == "visible":

        vis_parts.append(rem)

    elif state == "think":

        think_parts.append(rem)



    visible_str = re.sub(r"^\s+", "", "".join(vis_parts))

    think_str = "".join(think_parts)

    if not think_str.strip():

        think_str = ""



    # Strip complete leading leaked meta-monologue lines live, and hold back ambiguous partial first line

    visible_str = _strip_raw_tool_calls(visible_str)
    visible_str, leaked_prefix = _strip_leading_meta_monologue(visible_str)
    low_vis_trimmed = visible_str.lstrip().lower()
    tool_prefixes = ("```json", "```{", "<tool_call", "<function_call", "<tool", '{"tool_call"', '{"name":')
    if any(low_vis_trimmed.startswith(p) for p in tool_prefixes) and not any(c in low_vis_trimmed for c in ("```\n", "```\r\n", "</tool_call>", "</function_call>", "</tool>")):
        return "", think_str

    if leaked_prefix:

        think_str = (think_str + "\n" + leaked_prefix).strip() if think_str else leaked_prefix

    if visible_str and "\n" not in visible_str:

        low_vis = visible_str.lstrip().lower()

        suspect_prefixes = ("the user ", "i need to ", "let me ")

        if any(p.startswith(low_vis) or low_vis.startswith(p) for p in suspect_prefixes):

            # Hold back until newline reveals whether this line is internal monologue or real prose

            if len(low_vis) < 220:

                return "", think_str



    return visible_str, think_str





_INTERNAL_PLACEHOLDER_PATTERNS = (

    r"^\s*Executing system tool operation\.{0,3}\s*$",

    r"^\s*\[Executing tool operation to fulfill request\]\s*$",

    r"^\s*\[Called tools:[^\]]*\]\s*$",

    r"^\s*\[Tool execution step\]\s*$",

    r"^\s*\[Tool call requested\]\s*$",

)





_META_MONOLOGUE_LINE_RE = re.compile(

    r"^\s*(?:"

    r"the user (?:said|says|asked|wants|wrote|is asking|is saying|just said|greeted|inquires|sent|shared|provided|typed|entered|replied)|"

    r"i (?:need to|should|will|must|can) (?:respond|reply|answer|check|greet|run|use|address)|"

    r"let me (?:respond|reply|give a|check|run some tools|answer naturally|think|analyze|inspect|see)"

    r")\b[^\n]*$",

    re.IGNORECASE,

)





def _strip_leading_meta_monologue(text: str) -> Tuple[str, str]:

    """

    Separates leaked English internal monologue lines (e.g. 'The user asked ... Let me respond naturally.')

    from the actual assistant reply. Returns (clean_reply, extracted_monologue).

    """

    if not text:

        return "", ""

    lines = text.splitlines()

    monologue: List[str] = []

    idx = 0

    while idx < len(lines):

        stripped = lines[idx].strip()

        if not stripped:

            if monologue:

                idx += 1

                continue

            break

        if _META_MONOLOGUE_LINE_RE.match(stripped):

            monologue.append(stripped)

            idx += 1

            continue

        break

    if not monologue:

        return text.strip(), ""

    remaining = "\n".join(lines[idx:]).strip()

    return remaining, "\n".join(monologue).strip()





def _scrub_internal_markers(text: str) -> str:

    """Removes internal orchestrator placeholder strings if echoed by a model."""

    if not text:

        return ""

    cleaned = text

    for pat in _INTERNAL_PLACEHOLDER_PATTERNS:

        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE | re.MULTILINE)

    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()





def _format_tool_feedback(tc_name: str, tool_output: Dict[str, Any]) -> str:

    """Formats structured tool outputs cleanly into concise readable feedback for LLM reasoning."""

    if not isinstance(tool_output, dict):

        return str(tool_output)



    if tool_output.get("error"):

        err_lines = [f"Error: {tool_output['error']}"]

        if tool_output.get("suggestion"):

            err_lines.append(f"Suggestion: {tool_output['suggestion']}")

        if tool_output.get("available_categories"):

            err_lines.append("Available categories: " + ", ".join(tool_output["available_categories"]))

        if tool_output.get("available_countries"):

            err_lines.append("Available countries: " + ", ".join(tool_output["available_countries"]))

        return "\n".join(err_lines)



    if tc_name == "read_file" and "content" in tool_output:

        s_line = tool_output.get("start_line", 1)

        n_ret = tool_output.get("lines_returned", 0)

        tot_l = tool_output.get("total_lines", n_ret)

        e_line = s_line + n_ret - 1 if n_ret > 0 else s_line

        return f"[File: {tool_output.get('path', '')} | Lines {s_line}-{e_line} of {tot_l}]\n{tool_output.get('content', '')}"



    if tc_name == "list_rss_categories":

        countries = ", ".join(f"{c['name']} ({c['feed_count']})" for c in tool_output.get("countries", []))

        cats = ", ".join(f"{c['name']} ({c['feed_count']})" for c in tool_output.get("categories", []))

        return (

            f"RSS Directory Tree ({tool_output.get('total_countries', 0)} countries, "

            f"{tool_output.get('total_categories', 0)} categories)\n"

            f"- Countries: {countries}\n"

            f"- Topic Categories: {cats}\n"

            f"Next: {tool_output.get('next_step', '')}"

        )



    if tc_name == "get_rss_category_feeds":

        lines = [

            f"RSS Branch: {tool_output.get('category')} ({tool_output.get('section_type')}, "

            f"{tool_output.get('matched_feeds', tool_output.get('total_feeds', 0))} shown of {tool_output.get('total_feeds', 0)} feeds)"

        ]

        if tool_output.get("filter_applied"):

            lines.append(f"Filter applied: '{tool_output['filter_applied']}'")

        for idx, f in enumerate(tool_output.get("feeds", []), 1):

            lines.append(f"{idx}. {f.get('title', 'Feed')} -> {f.get('url', '')}")

        lines.append(f"IMPORTANT: {tool_output.get('next_step', '')}")

        return "\n".join(lines)



    if tc_name == "fetch_rss_feed":

        items = tool_output.get("items") or []

        statuses = tool_output.get("feed_statuses") or []

        ok_sources = [s.get("source") for s in statuses if s.get("ok") and s.get("item_count", 0) > 0]

        fail_sources = [f"{s.get('source', 'feed')} ({s.get('error', 'empty')})" for s in statuses if not (s.get("ok") and s.get("item_count", 0) > 0)]

        lines = [

            f"RSS Live Articles Digest | Category: {tool_output.get('category') or 'Direct URL'} | "

            f"Working feeds: {len(ok_sources)}/{tool_output.get('feeds_checked', len(statuses))} | "

            f"Total parsed: {tool_output.get('total_fetched', 0)}"

        ]

        if ok_sources:

            lines.append("Sources fetched: " + ", ".join(str(x) for x in ok_sources))

        if fail_sources:

            lines.append("Unavailable/skipped feeds: " + ", ".join(fail_sources[:6]))

        if tool_output.get("query"):

            lines.append(f"Query: '{tool_output['query']}' -> Matched: {tool_output.get('matched_count', len(items))}")



        display_items = items

        if not display_items and tool_output.get("latest_sample"):

            lines.append(f"Note: {tool_output.get('note', 'Showing latest available articles:')}")

            display_items = tool_output["latest_sample"]



        if display_items:

            lines.append("\nArticles:")

            for idx, it in enumerate(display_items, 1):

                pub = f" ({it['published']})" if it.get("published") else ""

                lines.append(f"{idx}. [{it.get('source', 'RSS')}] {it.get('title', '')}{pub}")

                if it.get("summary"):

                    lines.append(f"   Summary: {it['summary']}")

                if it.get("link"):

                    lines.append(f"   Link: {it['link']}")

            lines.append(

                "\nDirective: You now have live news articles with sources, dates, summaries, and links. "

                "Synthesize a clear, comprehensive response directly in the user's language with citations. "

                "Do NOT run shell/PowerShell commands to scrape websites."

            )

        else:

            lines.append("No articles could be parsed from those feeds. Try another RSS category, broader query, or web_search.")

        return "\n".join(lines)



    if tc_name == "web_search" and isinstance(tool_output.get("results"), list):

        lines = [f"Web Search ({tool_output.get('source', 'search')}) for '{tool_output.get('query', '')}':"]

        for idx, r in enumerate(tool_output["results"], 1):

            lines.append(f"{idx}. {r.get('title', '')}\n   URL: {r.get('url', '')}\n   Snippet: {r.get('snippet', '')}")

        return "\n".join(lines)



    val = tool_output.get("stdout") or tool_output.get("result") or json.dumps(tool_output, ensure_ascii=False)

    if isinstance(val, (dict, list)):

        val = json.dumps(val, ensure_ascii=False)

    return str(val)





class AgentOrchestrator:

    """

    Core Agent Orchestrator engine executing iterative multi-step reasoning,

    tool execution, approval pausing, feedback loops, and persistent conversation history.

    """

    _cancelled_convs = set()

    _active_turns = set()

    _active_tasks: Dict[str, asyncio.Task] = {}



    @classmethod

    def cancel_turn(cls, conversation_id: str):

        """Signals active orchestrator turns for this conversation to stop immediately."""

        cls._cancelled_convs.add(conversation_id)

        task = cls._active_tasks.get(conversation_id)

        if task and not task.done():

            task.cancel()

        cls._active_turns.discard(conversation_id)



    @classmethod

    def is_turn_active(cls, conversation_id: str) -> bool:

        """Returns True if the orchestrator is currently executing a turn for this conversation."""

        return conversation_id in cls._active_turns



    @classmethod

    async def _generate_ai_session_title(

        cls,

        conversation_id: str,

        user_prompt: str,

        adapter,

        model_name: str

    ):

        """Asynchronously uses the AI model to generate a concise, smart title for the conversation."""

        try:

            prompt_clean = user_prompt.strip()[:300]

            title_messages = [

                {

                    "role": "system",

                    "content": (

                        "You are an AI conversation title generator. Output ONLY a concise, high-level title (3 to 6 words) "

                        "describing the user's inquiry. Do NOT use quotation marks, punctuation, or explanations. "

                        "Match the user's language: if Persian, answer in Persian; if English, answer in English."

                    )

                },

                {"role": "user", "content": prompt_clean}

            ]

            collected = []

            async for chunk in adapter.chat_stream(

                model=model_name or "default",

                messages=title_messages,

                tools=None,

                temperature=0.3,

                max_tokens=60,

                enable_thinking=False

            ):

                if chunk.delta_text:

                    collected.append(chunk.delta_text)

            raw_title, _ = _strip_internal_tags("".join(collected))

            ai_title = raw_title.strip().strip('"\'`').replace("\n", " ")

            if ai_title:

                ai_title = re.sub(r'^[#*"\']+|[#*"\']+$', '', ai_title).strip()

                if len(ai_title) > 40:

                    ai_title = ai_title[:40].strip()

                if ai_title:

                    logger.info(f"AI generated session title for {conversation_id}: '{ai_title}'")

                    await ConversationRepository.update_conversation(conversation_id, {"title": ai_title})

                    await event_bus.publish(AgentEvent(

                        event_type="conversation_renamed",

                        conversation_id=conversation_id,

                        data={"title": ai_title}

                    ))

        except Exception as e:

            logger.warning(f"Could not generate AI session title for {conversation_id}: {e}")



    @classmethod

    async def run_turn(

        cls,

        conversation_id: str,

        user_prompt: Optional[str] = None,

        pre_approved_id: Optional[str] = None,

        enable_thinking: Optional[bool] = None,

        enable_search: Optional[bool] = None

    ) -> Dict[str, Any]:

        cls._cancelled_convs.discard(conversation_id)

        cls._active_turns.add(conversation_id)

        cls._active_tasks[conversation_id] = asyncio.current_task()

        is_paused_for_approval = False

        asst_msg_id = None

        cumulative_assistant_text = ""

        cumulative_thoughts = ""

        final_assistant_content = ""

        executed_tool_summaries = []



        try:

            conv = await ConversationRepository.get_conversation(conversation_id)

            if not conv:

                raise ValueError(f"Conversation {conversation_id} not found.")



            # Save user message if provided

            if user_prompt:

                await ConversationRepository.add_message(

                    conversation_id=conversation_id,

                    role="user",

                    content=user_prompt

                )



            provider_id = conv.get("provider_id")

            model_name = conv.get("model_id")

            workspace_path = conv.get("workspace_path") or settings.DEFAULT_WORKSPACE

            permission_mode = conv.get("permission_mode") or settings.DEFAULT_PERMISSION_MODE



            # Resolve valid model and provider if not explicitly set

            if not model_name:

                async with get_db() as db:

                    cursor = await db.execute(

                        "SELECT model_name, provider_id FROM provider_models WHERE model_name NOT LIKE '%embedding%' ORDER BY (model_name = 'gemini-3.8-flash') DESC, id ASC LIMIT 1"

                    )

                    m_row = await cursor.fetchone()

                    if m_row:

                        model_name = m_row["model_name"]

                        if not provider_id:

                            provider_id = m_row["provider_id"]



            if not provider_id and model_name:

                async with get_db() as db:

                    cursor = await db.execute("SELECT provider_id FROM provider_models WHERE model_name = ? LIMIT 1", (model_name,))

                    p_row = await cursor.fetchone()

                    if p_row:

                        provider_id = p_row["provider_id"]



            adapter = await ProviderRegistry.get_adapter_for_provider(provider_id)

            if not adapter:

                err_msg = f"No active provider adapter found for ID '{provider_id}'."

                logger.error(err_msg)

                await event_bus.publish(AgentEvent(

                    event_type="error",

                    conversation_id=conversation_id,

                    data={"message": err_msg}

                ))

                await event_bus.publish(AgentEvent(

                    event_type="done",

                    conversation_id=conversation_id,

                    data={"error": err_msg}

                ))

                return {"error": err_msg}



            # Determine if session title should be autonomously generated

            # ONLY on the initial message of a new session

            all_existing = await ConversationRepository.get_messages(conversation_id, limit=50)

            user_msg_count = len([m for m in all_existing if m.get("role") == "user"])

            is_initial_turn = user_msg_count <= 1

            cur_title = (conv.get("title") or "").strip()

            is_default_title = (

                not cur_title or

                cur_title in ("New Session", "New Conversation", "Live End-to-End Test Session", "Session") or

                cur_title.startswith("New Session") or

                cur_title.startswith("New Conversation")

            )

            should_generate_title = is_initial_turn and is_default_title



            # Autonomously set smart session title immediately on initial user message

            if should_generate_title and user_prompt:

                prompt_text_only = re.sub(r'<attachment\s+[^>]*?>[\s\S]*?</attachment>', '', user_prompt).strip()

                if not prompt_text_only:

                    att_names = re.findall(r'<attachment\s+[^>]*?name="([^"]+)"', user_prompt)

                    prompt_text_only = f"File: {att_names[0]}" if att_names else "Attached Files"

                clean_first_line = prompt_text_only.splitlines()[0].strip()

                words = clean_first_line.split()

                quick_title = " ".join(words[:6])

                if len(quick_title) > 36:

                    quick_title = quick_title[:33] + "..."

                if quick_title:

                    try:

                        await ConversationRepository.update_conversation(conversation_id, {"title": quick_title})

                        await event_bus.publish(AgentEvent(

                            event_type="conversation_renamed",

                            conversation_id=conversation_id,

                            data={"title": quick_title}

                        ))

                    except Exception as e:

                        logger.warning(f"Could not set initial session title: {e}")

                # AI title refinement runs after the main turn finishes so it does not collide on single-slot local inference servers



            # Detect active skill trigger if prompt begins with /command

            skill_cmd = None

            if user_prompt and user_prompt.strip().startswith("/"):

                first_token = user_prompt.strip().split()[0]

                if re.match(r"^/[a-zA-Z0-9_-]+$", first_token):

                    skill_cmd = first_token



            # Build System Prompt (only includes session title instruction if should_generate_title is True)

            system_prompt = await PromptEngine.build_system_prompt(

                agent_profile_id=conv.get("agent_profile_id"),

                system_prompt_id=conv.get("system_prompt_id"),

                workspace_path=workspace_path,

                conversation_id=conversation_id,

                include_tool_fallback=True,

                skill_command=skill_cmd,

                include_session_title=should_generate_title,

                enable_thinking=enable_thinking

            )



            # Create the ONE assistant message row for this turn upfront

            turn_asst_msg = await ConversationRepository.add_message(

                conversation_id=conversation_id,

                role="assistant",

                content="",

                thoughts="",

                tokens=0

            )

            asst_msg_id = turn_asst_msg["id"]



            in_turn_messages = []



            # If resuming from an approval decision (approved or denied), process it FIRST

            if pre_approved_id:

                try:

                    approval = await ExecutionRepository.get_approval(pre_approved_id)

                    if approval and approval.get("tool_call_id"):

                        tc = await ExecutionRepository.get_tool_call(approval["tool_call_id"])

                        if tc:

                            tc_name = tc.get("tool_name")

                            raw_args = tc.get("arguments_json", "{}")

                            args_dict = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})



                            if approval.get("status") == "denied":

                                logger.info(f"Pending tool call {tc['id']} ({tc_name}) denied by user.")

                                deny_output = {

                                    "status": "rejected",

                                    "error": "Execution denied by user.",

                                    "is_error": True,

                                }

                                await ExecutionRepository.record_tool_result(

                                    tool_call_id=tc["id"],

                                    stdout="",

                                    stderr="Execution denied by user.",

                                    exit_code=1,

                                    duration_ms=0,

                                    is_error=True,

                                    output_data=deny_output,

                                )

                                await event_bus.publish(AgentEvent(

                                    event_type="tool_call_result",

                                    conversation_id=conversation_id,

                                    data={"tool_call_id": tc["id"], "tool_name": tc_name, "result": deny_output},

                                ))

                                executed_tool_summaries.append(f"Skipped denied tool: {tc_name}")

                                in_turn_messages.append({"role": "assistant", "content": f"[Called tools: {tc_name}]"})

                                in_turn_messages.append({

                                    "role": "system",

                                    "content": (

                                        f"[TOOL EXECUTION FEEDBACK]\nThe user DENIED permission to execute `{tc_name}`. "

                                        "Do NOT request or retry this shell command. Answer the user's question directly using any information "

                                        "already retrieved or safe non-shell tools."

                                    ),

                                })

                            else:

                                ctx = {

                                    "conversation_id": conversation_id,

                                    "tool_call_id": tc["id"],

                                    "workspace_path": workspace_path,

                                    "permission_mode": permission_mode,

                                    "pre_approved_id": pre_approved_id,

                                }

                                logger.info(f"Executing approved tool call {tc['id']} ({tc_name}) for conversation {conversation_id}")

                                tool_output = await tool_registry.execute_tool(tc_name, args_dict, ctx)



                                if tc_name in ("write_file", "create_file", "edit_file"):

                                    p = args_dict.get("path") or "file"

                                    executed_tool_summaries.append(f"Edited 📄 {p.split('/')[-1].split(chr(92))[-1]}")

                                elif tc_name == "read_file":

                                    p = args_dict.get("path") or "file"

                                    executed_tool_summaries.append(f"Analyzed 📄 {p.split('/')[-1].split(chr(92))[-1]}")

                                elif tc_name in ("run_command", "powershell", "execute_command"):

                                    cmd = args_dict.get("CommandLine") or args_dict.get("command") or ""

                                    executed_tool_summaries.append(f"Ran command: {cmd[:50]}")

                                elif tc_name == "list_directory":

                                    p = args_dict.get("path") or "."

                                    executed_tool_summaries.append(f"Listed directory: {p.split('/')[-1].split(chr(92))[-1] or p}")

                                else:

                                    executed_tool_summaries.append(f"Ran {tc_name}")



                                stdout_str = _format_tool_feedback(tc_name, tool_output)

                                stderr_str = tool_output.get("stderr") or ""

                                exit_code = tool_output.get("exit_code", 0)

                                is_err = bool(tool_output.get("is_error")) or tool_output.get("status") == "failed" or bool(tool_output.get("error"))



                                await ExecutionRepository.record_tool_result(

                                    tool_call_id=tc["id"],

                                    stdout=stdout_str,

                                    stderr=stderr_str,

                                    exit_code=exit_code,

                                    duration_ms=tool_output.get("duration_ms", 0),

                                    is_error=is_err,

                                    output_data=tool_output,

                                )

                                await event_bus.publish(AgentEvent(

                                    event_type="tool_call_result",

                                    conversation_id=conversation_id,

                                    data={"tool_call_id": tc["id"], "tool_name": tc_name, "result": tool_output},

                                ))

                                fb_body = stdout_str[:12000]

                                if is_err and stderr_str:

                                    fb_body += f"\nError: {stderr_str}"

                                in_turn_messages.append({"role": "assistant", "content": f"[Called tools: {tc_name}]"})

                                in_turn_messages.append({"role": "system", "content": f"[TOOL EXECUTION FEEDBACK]\nTool '{tc_name}' Result:\n{fb_body}"})

                except Exception as ex_app:

                    logger.error(f"Error resuming approval decision {pre_approved_id}: {ex_app}", exc_info=True)

                finally:

                    pre_approved_id = None



            # Multi-step Iteration Loop

            iteration = 0

            max_iterations = min(settings.MAX_AGENT_ITERATIONS, 25)

            stream_recovery_retries = 0

            title_extracted = not should_generate_title

            last_tokens = 0

            call_history_counts = {}

            force_text_next = False

            loop_breaks = 0

            meta_monologue_retries = 0



            while iteration < max_iterations:

                if conversation_id in cls._cancelled_convs:

                    logger.info(f"Agent turn for {conversation_id} stopped by user cancellation.")

                    partial = cumulative_assistant_text.strip()

                    if partial and asst_msg_id:

                        await ConversationRepository.update_message(asst_msg_id, partial)

                    await event_bus.publish(AgentEvent(

                        event_type="done",

                        conversation_id=conversation_id,

                        data={"cancelled": True, "message_id": asst_msg_id}

                    ))

                    return {"status": "cancelled", "conversation_id": conversation_id}



                iteration += 1

                await event_bus.publish(AgentEvent(

                    event_type="status",

                    conversation_id=conversation_id,

                    data={"status": "thinking", "iteration": iteration}

                ))



                # Determine if current model supports multimodal vision

                model_has_vision = False

                try:

                    async with get_db() as db:

                        cur_m = await db.execute(

                            "SELECT supports_vision FROM provider_models WHERE (model_name = ? OR id = ? OR display_name = ?) LIMIT 1;",

                            (model_name, model_name, model_name)

                        )

                        row_m = await cur_m.fetchone()

                        if row_m and row_m["supports_vision"] is not None:

                            model_has_vision = bool(row_m["supports_vision"])

                        else:

                            from backend.app.providers.openai_compatible import detect_vision_support

                            model_has_vision = detect_vision_support(model_name)

                except Exception:

                    from backend.app.providers.openai_compatible import detect_vision_support

                    model_has_vision = detect_vision_support(model_name)



                if model_has_vision and "Desktop GUI & Screen Automation Instructions" not in system_prompt:
                    from backend.app.tools.system.desktop_automation import _get_screen_size
                    scr_w, scr_h = _get_screen_size()
                    system_prompt += (
                        f"\n\n### Desktop GUI & Screen Automation Instructions:\n"
                    f"CRITICAL DIRECTIVE: You have DIRECT physical control of the user's mouse and keyboard via the `desktop_control` tool. NEVER tell the user you lack physical or graphical control of their browser or desktop, because you HAVE full control through `desktop_control`! Immediately invoke `desktop_control` whenever the user asks you to click, type, open browser, or interact with screen elements.\n"
                        f"You have access to the `desktop_control` tool to visually inspect and operate the user's desktop mouse and keyboard on Windows.\n"
                        f"- Current Screen Resolution: {scr_w}x{scr_h}. Coordinates you specify are automatically mapped to physical screen pixels.\n"
                        f"- Instant Screen OCR & UI Element Detection:\n"
                        f"  * Call `desktop_control(action='find_text', text='Search', click=True)` to instantly locate any button, menu, or text on screen (like in Photoshop, Chrome, etc.) and click it automatically in one step!\n"
                        f"  * Call `desktop_control(action='ocr')` to scan the screen and receive a list of all visible text elements with their exact (x, y) coordinates.\n"
                        f"- Visual Inspection:\n"
                        f"  * Call `desktop_control(action='screenshot')` to capture and view the desktop screen at any point.\n"
                        f"  * Always examine the visual screenshot or OCR results to find exact visual element coordinates before clicking.\n"
                        f"- Interacting with Applications & Web Browsers:\n"
                        f"  * To search Google or open a website: Call `desktop_control(action='open_url', text='https://www.google.com')`. This opens the user's browser directly to that site! Then call `action='screenshot'` to view the page.\n"
                        f"  * To click and type into any field (search box, form, address bar): Use `desktop_control(action='type', x=..., y=..., text='...', press_enter=True)`. It will automatically click at (x, y) to focus the box, type the text, and press Enter.\n"
                        f"  * To launch an app by name: Call `desktop_control(action='open_app', text='chrome')` (or 'msedge', 'notepad', 'calc', etc.), or call `action='press_key', key='win+r'` and type the app name.\n"
                        f"  * Taskbar is at the bottom of the screen (y ~ {scr_h - 25}). You can click icons on the taskbar to open or switch apps.\n"
                        f"  * Common hotkeys: 'enter', 'tab', 'win+r', 'alt+d' (focus address bar), 'ctrl+t' (new tab), 'ctrl+w' (close tab), 'ctrl+l' (address bar).\n"
                        f"  * After performing an action, call `action='screenshot'` to confirm the result.\n"
                    )

                # Retrieve conversation messages (excluding placeholder) and unpack attachments for LLM
                raw_messages = await ConversationRepository.get_messages(conversation_id, limit=50)
                formatted_messages = [{"role": "system", "content": system_prompt}]
                last_user_msg = next((m for m in reversed(raw_messages) if m.get("role") == "user" and m.get("id") != asst_msg_id), None)

                for m in raw_messages:
                    if m["id"] == asst_msg_id:
                        continue
                    if m.get("role") != "user":
                        formatted_messages.append({"role": m["role"], "content": m["content"]})
                        continue

                    raw_user_content = m.get("content") or ""
                    is_last_user_msg = bool(last_user_msg and m["id"] == last_user_msg["id"])

                    # Check for attachment tags: <attachment type="..." name="..." mime="..." size="...">content</attachment>
                    att_matches = list(re.finditer(r'<attachment\s+([^>]*?)>([\s\S]*?)</attachment>', raw_user_content, re.IGNORECASE))
                    clean_user_prompt = re.sub(r'<attachment\s+[^>]*?>[\s\S]*?</attachment>', '', raw_user_content).strip() if att_matches else raw_user_content.strip()
                    text_file_sections = []
                    image_parts = []

                    for match in att_matches:
                        attr_str = match.group(1)
                        att_body = match.group(2).strip()
                        type_match = re.search(r'type="([^"]+)"', attr_str, re.IGNORECASE)
                        name_match = re.search(r'name="([^"]+)"', attr_str, re.IGNORECASE)
                        att_type = type_match.group(1).lower() if type_match else "text"
                        att_name = name_match.group(1) if name_match else "file.txt"
                        ext = att_name.split(".")[-1] if "." in att_name else "text"

                        if att_type == "image":
                            # Always send attached images as multimodal image_url parts
                            image_parts.append({"type": "image_url", "image_url": {"url": att_body}})
                        elif att_type in ("paste", "text"):
                            header_title = "Pasted Text Snippet" if att_type == "paste" else f"Attached File: {att_name}"
                            text_file_sections.append(f"[{header_title}]\n```{ext}\n{att_body}\n```")

                    # If this is the active user turn and model has vision, auto-attach real-time desktop screenshot for GUI requests
                    if model_has_vision and is_last_user_msg and not image_parts:
                        gui_keywords = ("\u0645\u0648\u0633", "\u06a9\u06cc\u0628\u0631\u062f", "\u06a9\u06cc\u0628\u0648\u0631\u062f", "\u062f\u0633\u06a9\u062a\u0627\u067e", "\u0627\u0633\u06a9\u0631\u06cc\u0646", "\u06a9\u0644\u06cc\u06a9", "\u0645\u0631\u0648\u0631\u06af\u0631", "\u0641\u062a\u0648\u0634\u0627\u067e", "\u062a\u0627\u06cc\u067e", "mouse", "keyboard", "desktop", "screen", "click", "browser", "photoshop", "gui", "google")
                        if any(kw in raw_user_content.lower() for kw in gui_keywords):
                            try:
                                from backend.app.tools.system.desktop_automation import _take_screenshot
                                auto_shot = _take_screenshot()
                                if auto_shot.get("image_base64"):
                                    image_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{auto_shot['image_base64']}"}})
                                    text_file_sections.append(
                                        f"[LIVE DESKTOP SCREENSHOT - {auto_shot.get('screen_width')}x{auto_shot.get('screen_height')}]: "
                                        "A real-time screenshot of the user's active desktop has been captured and attached to this message. "
                                        "Use it to visually locate the exact window, address bar, icon, or search box before clicking or typing."
                                    )
                            except Exception as exc:
                                logger.warning(f"Auto desktop screenshot capture skipped: {exc}")



                    for match in att_matches:

                        attr_str = match.group(1)

                        att_body = match.group(2).strip()

                        type_match = re.search(r'type="([^"]+)"', attr_str, re.IGNORECASE)

                        name_match = re.search(r'name="([^"]+)"', attr_str, re.IGNORECASE)

                        att_type = type_match.group(1).lower() if type_match else "text"

                        att_name = name_match.group(1) if name_match else "file.txt"

                        ext = att_name.split(".")[-1] if "." in att_name else "text"



                        if att_type == "image":

                            # Always send attached images as multimodal image_url parts

                            image_parts.append({"type": "image_url", "image_url": {"url": att_body}})

                        elif att_type in ("paste", "text"):

                            header_title = "Pasted Text Snippet" if att_type == "paste" else f"Attached File: {att_name}"

                            text_file_sections.append(f"[{header_title}]\n```{ext}\n{att_body}\n```")



                    combined_text_parts = []

                    if text_file_sections:

                        combined_text_parts.append("\n\n".join(text_file_sections))

                    if clean_user_prompt:

                        combined_text_parts.append(clean_user_prompt)



                    final_text_content = "\n\n".join(combined_text_parts).strip()



                    if image_parts:

                        if not model_has_vision:

                            refusal_msg = (

                                f"Model **{model_name}** is a text-only model and does not support image or multimodal input.\n\n"

                                f"Please select a multimodal vision model (such as a model with multimodal projector / mmproj loaded, Qwen-VL, LLaVA, or GPT-4o) to analyze images."

                            )

                            await ConversationRepository.update_message(

                                message_id=asst_msg_id,

                                content=refusal_msg,

                                thoughts=None,

                                tokens=0

                            )

                            await event_bus.publish(AgentEvent(

                                event_type="done",

                                conversation_id=conversation_id,

                                data={"message_id": asst_msg_id, "content": refusal_msg}

                            ))

                            return



                        multimodal_parts = []

                        if final_text_content:

                            multimodal_parts.append({"type": "text", "text": final_text_content})

                        else:

                            multimodal_parts.append({"type": "text", "text": "Please inspect and analyze the attached image."})

                        multimodal_parts.extend(image_parts)

                        formatted_messages.append({"role": "user", "content": multimodal_parts})

                    else:

                        formatted_messages.append({"role": "user", "content": final_text_content or raw_user_content})



                # Append in-memory turn messages (preludes + tool results)

                messages_for_turn = formatted_messages + in_turn_messages



                # Prune to fit model context limit

                context_messages, token_stats = ContextManager.prune_context(

                    system_prompt=system_prompt,

                    messages=messages_for_turn

                )

                last_tokens = token_stats.get("total_estimated_tokens", 0)



                # Prepare tool definitions (disabled if breaking a repetitive loop)

                available_tools = None if force_text_next else tool_registry.get_openai_tools()

                if available_tools:

                    if enable_search is False:

                        available_tools = [t for t in available_tools if t.get("function", {}).get("name") != "web_search"]

                    # Desktop GUI automation tool is strictly available for vision-capable models only

                    if not model_has_vision:

                        available_tools = [t for t in available_tools if t.get("function", {}).get("name") != "desktop_control"]

                force_text_next = False



                # Stream from model

                current_turn_text = ""

                current_turn_thought = ""

                tool_calls_to_execute: List[Dict[str, Any]] = []

                emitted_visible_len = 0

                emitted_inline_think_len = 0



                stream_token_count = 0

                last_stream_save = time.time()

                executed_screenshot_b64 = None



                async for chunk in adapter.chat_stream(

                    model=model_name or "default",

                    messages=context_messages,

                    tools=available_tools,

                    enable_thinking=enable_thinking

                ):

                    if conversation_id in cls._cancelled_convs:

                        break



                    if chunk.delta_text:

                        current_turn_text += chunk.delta_text

                        stream_token_count += 1



                        # Real-time extraction of AI-determined session title (only if initial turn)

                        if not title_extracted and ("<session_title>" in current_turn_text or "<title>" in current_turn_text):

                            title_m = re.search(r"<(?:session_title|title)>(.*?)</(?:session_title|title)>", current_turn_text, re.DOTALL)

                            if title_m:

                                ai_title = title_m.group(1).strip()

                                ai_title = re.sub(r'^[#*"\']+|[#*"\']+$', '', ai_title).strip()

                                if len(ai_title) > 45:

                                    ai_title = ai_title[:45].strip()

                                if ai_title:

                                    title_extracted = True

                                    logger.info(f"AI autonomously set session title: '{ai_title}'")

                                    await ConversationRepository.update_conversation(conversation_id, {"title": ai_title})

                                    await event_bus.publish(AgentEvent(

                                        event_type="conversation_renamed",

                                        conversation_id=conversation_id,

                                        data={"title": ai_title}

                                    ))



                        visible_safe, inline_think_safe = _compute_safe_stream_views(current_turn_text)

                        if len(inline_think_safe) > emitted_inline_think_len:

                            new_inline_thk = inline_think_safe[emitted_inline_think_len:]

                            emitted_inline_think_len = len(inline_think_safe)

                            current_turn_thought += new_inline_thk

                            if enable_thinking is not False:

                                await event_bus.publish(AgentEvent(

                                    event_type="thought",

                                    conversation_id=conversation_id,

                                    data={"delta": new_inline_thk}

                                ))



                        if len(visible_safe) > emitted_visible_len:

                            new_vis = visible_safe[emitted_visible_len:]

                            emitted_visible_len = len(visible_safe)

                            await event_bus.publish(AgentEvent(

                                event_type="token",

                                conversation_id=conversation_id,

                                data={"delta": new_vis}

                            ))



                        # Incremental real-time persistence so page refresh or navigation never loses text

                        now_ts = time.time()

                        if (stream_token_count % 10 == 0 or (now_ts - last_stream_save) >= 1.0) and asst_msg_id:

                            last_stream_save = now_ts

                            clean_so_far, _ = _strip_internal_tags(current_turn_text)

                            clean_so_far = _strip_raw_tool_calls(clean_so_far)

                            clean_so_far, _ = _strip_leading_meta_monologue(clean_so_far)

                            combined_so_far = (cumulative_assistant_text.strip() + ("\n\n" if cumulative_assistant_text.strip() and clean_so_far else "") + clean_so_far).strip()

                            if combined_so_far:

                                try:

                                    await ConversationRepository.update_message(

                                        message_id=asst_msg_id,

                                        content=combined_so_far,

                                        thoughts=(cumulative_thoughts + current_turn_thought).strip() or None,

                                        tokens=last_tokens

                                    )

                                except Exception:

                                    pass



                    if chunk.delta_thought and enable_thinking is not False:

                        current_turn_thought += chunk.delta_thought

                        await event_bus.publish(AgentEvent(

                            event_type="thought",

                            conversation_id=conversation_id,

                            data={"delta": chunk.delta_thought}

                        ))



                    if chunk.tool_calls:

                        tool_calls_to_execute.extend(chunk.tool_calls)



                if conversation_id in cls._cancelled_convs:

                    partial = cumulative_assistant_text.strip()

                    if partial and asst_msg_id:

                        await ConversationRepository.update_message(asst_msg_id, partial)

                    await event_bus.publish(AgentEvent(

                        event_type="done",

                        conversation_id=conversation_id,

                        data={"cancelled": True, "message_id": asst_msg_id}

                    ))

                    return {"status": "cancelled", "conversation_id": conversation_id}



                # Fallback structured tool calls in generated text

                if not tool_calls_to_execute and current_turn_text:

                    fallback_calls = ToolRouter.extract_fallback_tool_calls(current_turn_text)

                    if fallback_calls:

                        tool_calls_to_execute.extend(fallback_calls)



                # Filter out repetitive loop tool calls

                raw_calls_count = len(tool_calls_to_execute)

                filtered_calls = []

                for tc_item in tool_calls_to_execute:

                    tc_sig = f"{tc_item.get('name')}:{tc_item.get('arguments')}"

                    call_history_counts[tc_sig] = call_history_counts.get(tc_sig, 0) + 1

                    if call_history_counts[tc_sig] > 1:

                        logger.warning(f"Preventing duplicate tool call for {tc_sig}")

                        in_turn_messages.append({

                            "role": "system",

                            "content": f"[SYSTEM DIRECTIVE] Tool '{tc_item.get('name')}' has already been executed with these exact parameters in this turn. DO NOT call it again. Use the existing result above to answer the user now."

                        })

                    else:

                        filtered_calls.append(tc_item)

                tool_calls_to_execute = filtered_calls



                # Watchdog recovery

                is_connection_error = (

                    "[Stream connection error" in current_turn_text or

                    "[Provider API Error" in current_turn_text

                )

                if is_connection_error and not tool_calls_to_execute:

                    stream_recovery_retries += 1

                    if stream_recovery_retries <= 3:

                        logger.warning(f"Connection glitch on {conversation_id} (watchdog recovery {stream_recovery_retries}/3). Re-engaging agent...")

                        await event_bus.publish(AgentEvent(

                            event_type="status",

                            conversation_id=conversation_id,

                            data={"status": "reconnecting", "message": f"Network stream interrupted. Watchdog auto-recovering (attempt {stream_recovery_retries}/3)..."}

                        ))

                        await asyncio.sleep(2.0 * stream_recovery_retries)

                        continue



                # Strip internal <think>, <session_title>, <title> tags, placeholders, and leaked English monologue cleanly

                clean_assistant_text, _ = _strip_internal_tags(current_turn_text)

                clean_assistant_text = _strip_raw_tool_calls(clean_assistant_text)

                clean_assistant_text = _scrub_internal_markers(clean_assistant_text)

                clean_assistant_text, leaked_mono = _strip_leading_meta_monologue(clean_assistant_text)

                if leaked_mono and enable_thinking is not False:

                    current_turn_thought = (current_turn_thought + "\n" + leaked_mono).strip()



                # If all tool calls were suppressed due to repetition, force a synthesis turn without tools

                if raw_calls_count > 0 and not tool_calls_to_execute and loop_breaks < 2:

                    loop_breaks += 1

                    force_text_next = True

                    in_turn_messages.append({

                        "role": "system",

                        "content": "[SYSTEM DIRECTIVE] Repeated tool calls were suppressed. Do NOT mention calling tools. Synthesize all retrieved tool data above and provide a complete, well-structured final answer in the user's language right now."

                    })

                    continue



                # If model emitted ONLY leaked internal monologue without an actual user reply, retry cleanly without tools

                if not tool_calls_to_execute and leaked_mono and not clean_assistant_text and meta_monologue_retries < 1:

                    meta_monologue_retries += 1

                    force_text_next = True

                    in_turn_messages.append({

                        "role": "system",

                        "content": "[SYSTEM DIRECTIVE] You only emitted internal planning commentary without answering the user. Output ONLY your direct, friendly final reply in the user's exact language right now (no English meta-notes)."

                    })

                    continue



                if current_turn_thought and enable_thinking is not False:

                    cumulative_thoughts += current_turn_thought + "\n"



                # If NO tool calls were requested, this is the final answer!

                if not tool_calls_to_execute:

                    if cumulative_assistant_text.strip() and clean_assistant_text:

                        if not clean_assistant_text.startswith(cumulative_assistant_text.strip()[:30]):

                            final_assistant_content = (cumulative_assistant_text.strip() + "\n\n" + clean_assistant_text).strip()

                        else:

                            final_assistant_content = clean_assistant_text

                    elif clean_assistant_text:

                        final_assistant_content = clean_assistant_text

                    else:

                        final_assistant_content = cumulative_assistant_text.strip()



                    # Update the ONE assistant message in the database with final content

                    await ConversationRepository.update_message(

                        message_id=asst_msg_id,

                        content=final_assistant_content,

                        thoughts=cumulative_thoughts.strip() or None,

                        tokens=last_tokens

                    )



                    await event_bus.publish(AgentEvent(

                        event_type="done",

                        conversation_id=conversation_id,

                        data={"message_id": asst_msg_id, "content": final_assistant_content}

                    ))

                    if should_generate_title and not title_extracted and user_prompt:

                        asyncio.create_task(cls._generate_ai_session_title(conversation_id, user_prompt, adapter, model_name))

                    break



                # Tool calls exist: record intermediate prelude and execute tools

                if clean_assistant_text:

                    cumulative_assistant_text += clean_assistant_text + "\n\n"

                    in_turn_messages.append({"role": "assistant", "content": clean_assistant_text})

                else:

                    tc_names = ", ".join(tc.get("name", "tool") for tc in tool_calls_to_execute)

                    in_turn_messages.append({"role": "assistant", "content": f"[Called tools: {tc_names}]"})



                # Execute Tool Calls

                tool_results_feedback = []



                for tc in tool_calls_to_execute:

                    if conversation_id in cls._cancelled_convs:

                        break



                    tc_name = tc.get("name")

                    raw_args = tc.get("arguments", "{}")

                    if isinstance(raw_args, str):

                        try:

                            args_dict = json.loads(raw_args)

                        except Exception:

                            args_dict = {"raw": raw_args}

                    else:

                        args_dict = raw_args



                    tool_def = tool_registry.get_tool(tc_name)

                    risk_level = tool_def.risk_level if tool_def else "MODERATE"



                    # Record tool call in DB linked to the one assistant message

                    db_tool_call = await ExecutionRepository.create_tool_call(

                        message_id=asst_msg_id,

                        conversation_id=conversation_id,

                        tool_name=tc_name,

                        arguments=args_dict,

                        risk_level=risk_level,

                        status="running"

                    )



                    await event_bus.publish(AgentEvent(

                        event_type="tool_call_start",

                        conversation_id=conversation_id,

                        data={

                            "tool_call_id": db_tool_call["id"],

                            "tool_name": tc_name,

                            "arguments": args_dict,

                            "risk_level": risk_level

                        }

                    ))



                    ctx = {

                        "conversation_id": conversation_id,

                        "tool_call_id": db_tool_call["id"],

                        "workspace_path": workspace_path,

                        "permission_mode": permission_mode,

                        "pre_approved_id": pre_approved_id

                    }



                    tool_start_time = time.perf_counter()

                    heartbeat_stop = asyncio.Event()



                    async def _heartbeat_sender():

                        while not heartbeat_stop.is_set():

                            try:

                                await asyncio.wait_for(heartbeat_stop.wait(), timeout=4.0)

                            except asyncio.TimeoutError:

                                elapsed = round(time.perf_counter() - tool_start_time, 1)

                                await event_bus.publish(AgentEvent(

                                    event_type="heartbeat",

                                    conversation_id=conversation_id,

                                    data={"tool_name": tc_name, "elapsed_seconds": elapsed, "status": "executing"}

                                ))



                    heartbeat_task = asyncio.create_task(_heartbeat_sender())

                    try:

                        tool_output = await tool_registry.execute_tool(tc_name, args_dict, ctx)

                    finally:

                        heartbeat_stop.set()

                        heartbeat_task.cancel()



                    if tool_output.get("status") == "waiting_approval":

                        is_paused_for_approval = True

                        await event_bus.publish(AgentEvent(

                            event_type="approval_required",

                            conversation_id=conversation_id,

                            data={

                                "approval_id": tool_output.get("approval_id"),

                                "tool_call_id": db_tool_call["id"],

                                "tool_name": tc_name,

                                "command": tool_output.get("command", ""),

                                "risk_level": tool_output.get("risk_level", "MODERATE"),

                                "message": tool_output.get("message")

                            }

                        ))

                        await event_bus.publish(AgentEvent(

                            event_type="done",

                            conversation_id=conversation_id,

                            data={"waiting_approval": True, "approval_id": tool_output.get("approval_id")}

                        ))

                        return {

                            "status": "waiting_approval",

                            "approval_id": tool_output.get("approval_id"),

                            "message": "Operation paused waiting for user approval."

                        }



                    # Record completion

                    if tc_name in ("write_file", "create_file", "edit_file"):

                        p = args_dict.get("path") or "file"

                        executed_tool_summaries.append(f"Edited 📄 {p.split('/')[-1].split(chr(92))[-1]}")

                    elif tc_name == "read_file":

                        p = args_dict.get("path") or "file"

                        executed_tool_summaries.append(f"Analyzed 📄 {p.split('/')[-1].split(chr(92))[-1]}")

                    elif tc_name in ("run_command", "powershell", "execute_command"):

                        cmd = args_dict.get("CommandLine") or args_dict.get("command") or ""

                        executed_tool_summaries.append(f"Ran command: {cmd[:50]}")

                    elif tc_name == "list_directory":

                        p = args_dict.get("path") or "."

                        executed_tool_summaries.append(f"Listed directory: {p.split('/')[-1].split(chr(92))[-1] or p}")

                    else:

                        executed_tool_summaries.append(f"Ran {tc_name}")



                    stdout_str = _format_tool_feedback(tc_name, tool_output)

                    stderr_str = tool_output.get("stderr") or ""

                    exit_code = tool_output.get("exit_code", 0)

                    is_err = bool(tool_output.get("is_error")) or tool_output.get("status") == "failed" or bool(tool_output.get("error"))



                    await ExecutionRepository.record_tool_result(

                        tool_call_id=db_tool_call["id"],

                        stdout=stdout_str,

                        stderr=stderr_str,

                        exit_code=exit_code,

                        duration_ms=tool_output.get("duration_ms", 0),

                        is_error=is_err,

                        output_data=tool_output

                    )



                    await event_bus.publish(AgentEvent(

                        event_type="tool_call_result",

                        conversation_id=conversation_id,

                        data={

                            "tool_call_id": db_tool_call["id"],

                            "tool_name": tc_name,

                            "result": tool_output

                        }

                    ))



                    # Allow larger tool output (12000 chars) so read_file doesn't truncate mid-file and trigger repetitive re-reads

                    MAX_FB_CHARS = 12000

                    trimmed_stdout = stdout_str

                    if len(trimmed_stdout) > MAX_FB_CHARS:

                        half = MAX_FB_CHARS // 2

                        omitted = len(trimmed_stdout) - MAX_FB_CHARS

                        trimmed_stdout = trimmed_stdout[:half] + f"\n\n... [Output truncated: {omitted} characters omitted] ...\n\n" + trimmed_stdout[-half:]



                    feedback_item = f"Tool '{tc_name}' Result:\n{trimmed_stdout}"

                    if is_err and stderr_str:

                        feedback_item += f"\nError: {stderr_str}"

                    tool_results_feedback.append(feedback_item)



                    # If desktop_control captured a screenshot, collect base64 image for multimodal inspection

                    if tc_name == "desktop_control" and tool_output.get("image_base64"):

                        executed_screenshot_b64 = tool_output["image_base64"]



                # Append tool results into in-memory context (without polluting the DB!)

                if tool_results_feedback:

                    feedback_prompt = "\n\n".join(tool_results_feedback)

                    in_turn_messages.append({"role": "system", "content": f"[TOOL EXECUTION FEEDBACK]\n{feedback_prompt}"})



                if model_has_vision and executed_screenshot_b64:

                    in_turn_messages.append({

                        "role": "user",

                        "content": [

                            {"type": "text", "text": "[DESKTOP SCREENSHOT] Current screen visual frame:"},

                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{executed_screenshot_b64}"}}

                        ]

                    })



                # Reserve final iteration strictly for synthesis if loop is near exhaustion

                if iteration >= max_iterations - 1:

                    force_text_next = True

                    in_turn_messages.append({

                        "role": "system",

                        "content": "[SYSTEM DIRECTIVE] Final response step reached. Synthesize all retrieved results into a clear, comprehensive final answer in the user's language now."

                    })



                # Progressively persist accumulated progress into DB so page refresh retains state

                if asst_msg_id and cumulative_assistant_text.strip():

                    try:

                        await ConversationRepository.update_message(

                            message_id=asst_msg_id,

                            content=cumulative_assistant_text.strip(),

                            thoughts=cumulative_thoughts.strip() or None,

                            tokens=last_tokens

                        )

                    except Exception:

                        pass



            # Mandatory final synthesis pass if loop exited after tools without producing a non-tool final answer

            if (not final_assistant_content or not final_assistant_content.strip()) and executed_tool_summaries:

                try:

                    synthesis_messages = formatted_messages + in_turn_messages + [{

                        "role": "system",

                        "content": "[SYSTEM DIRECTIVE] Summarize all tool results above and deliver a complete, well-structured final answer in the user's language now."

                    }]

                    ctx_synth, _ = ContextManager.prune_context(system_prompt=system_prompt, messages=synthesis_messages)

                    synth_raw = ""

                    synth_emitted = 0

                    async for schunk in adapter.chat_stream(

                        model=model_name or "default",

                        messages=ctx_synth,

                        tools=None,

                        enable_thinking=False

                    ):

                        if conversation_id in cls._cancelled_convs:

                            break

                        if schunk.delta_text:

                            synth_raw += schunk.delta_text

                            vis_s, _ = _compute_safe_stream_views(synth_raw)

                            if len(vis_s) > synth_emitted:

                                delta_s = vis_s[synth_emitted:]

                                synth_emitted = len(vis_s)

                                await event_bus.publish(AgentEvent(

                                    event_type="token",

                                    conversation_id=conversation_id,

                                    data={"delta": delta_s}

                                ))

                    clean_synth, _ = _strip_internal_tags(synth_raw)

                    clean_synth = _strip_raw_tool_calls(clean_synth)

                    clean_synth = _scrub_internal_markers(clean_synth)

                    if clean_synth:

                        final_assistant_content = (

                            (cumulative_assistant_text.strip() + "\n\n" + clean_synth).strip()

                            if cumulative_assistant_text.strip()

                            else clean_synth

                        )

                except Exception as synth_err:

                    logger.warning(f"Final synthesis fallback warning: {synth_err}")



            # Ensure done event is published with robust fallback content

            if not final_assistant_content or not final_assistant_content.strip():

                if cumulative_assistant_text.strip():

                    final_assistant_content = cumulative_assistant_text.strip()

                elif executed_tool_summaries:

                    summary_bullets = "\n".join(f"- {s}" for s in executed_tool_summaries)

                    final_assistant_content = f"I have executed the following actions:\n\n{summary_bullets}\n\nTask completed successfully."

                else:

                    final_assistant_content = "Task completed successfully."



            if asst_msg_id:

                await ConversationRepository.update_message(

                    message_id=asst_msg_id,

                    content=final_assistant_content,

                    thoughts=cumulative_thoughts.strip() or None,

                    tokens=last_tokens

                )

            await event_bus.publish(AgentEvent(

                event_type="done",

                conversation_id=conversation_id,

                data={"message_id": asst_msg_id, "content": final_assistant_content}

            ))



            if should_generate_title and not title_extracted and user_prompt:

                asyncio.create_task(cls._generate_ai_session_title(conversation_id, user_prompt, adapter, model_name))



            return {

                "status": "completed",

                "conversation_id": conversation_id,

                "content": final_assistant_content

            }



        except Exception as e:

            logger.error(f"Error in AgentOrchestrator.run_turn for {conversation_id}: {e}", exc_info=True)

            if asst_msg_id:

                fallback_content = cumulative_assistant_text.strip()

                if not fallback_content and executed_tool_summaries:

                    summary_bullets = "\n".join(f"- {s}" for s in executed_tool_summaries)

                    fallback_content = f"The following operations were completed before interruption:\n\n{summary_bullets}"

                if not fallback_content:

                    fallback_content = f"Execution interrupted: {str(e)}"

                try:

                    await ConversationRepository.update_message(asst_msg_id, fallback_content)

                except Exception:

                    pass

            await event_bus.publish(AgentEvent(

                event_type="error",

                conversation_id=conversation_id,

                data={"message": f"Execution error: {str(e)}"}

            ))

            # Also emit terminal done event so frontend never hangs

            await event_bus.publish(AgentEvent(

                event_type="done",

                conversation_id=conversation_id,

                data={"error": str(e)}

            ))

            return {"status": "error", "error": str(e)}

        except asyncio.CancelledError:

            logger.info(f"Agent turn for {conversation_id} task cancelled.")

            await event_bus.publish(AgentEvent(

                event_type="done",

                conversation_id=conversation_id,

                data={"cancelled": True, "message_id": asst_msg_id}

            ))

            return {"status": "cancelled", "conversation_id": conversation_id}

        finally:

            cls._active_turns.discard(conversation_id)

            cls._cancelled_convs.discard(conversation_id)

            cls._active_tasks.pop(conversation_id, None)

