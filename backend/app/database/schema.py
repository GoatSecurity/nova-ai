import aiosqlite
import json
from datetime import datetime
from backend.app.database.connection import get_db
from backend.app.core.logging import logger
from backend.app.core.config import settings

CREATE_TABLES_SQL = """
-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    provider_id TEXT,
    model_id TEXT,
    agent_profile_id TEXT,
    system_prompt_id TEXT,
    workspace_path TEXT,
    permission_mode TEXT DEFAULT 'allow_safe',
    is_pinned INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    thoughts TEXT,
    tokens INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Tool calls
CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    risk_level TEXT NOT NULL, -- 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'
    status TEXT NOT NULL, -- 'pending', 'waiting_approval', 'approved', 'rejected', 'running', 'completed', 'failed', 'cancelled'
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Tool results
CREATE TABLE IF NOT EXISTS tool_results (
    id TEXT PRIMARY KEY,
    tool_call_id TEXT NOT NULL UNIQUE,
    stdout TEXT,
    stderr TEXT,
    exit_code INTEGER,
    duration_ms INTEGER,
    is_error INTEGER DEFAULT 0,
    output_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tool_call_id) REFERENCES tool_calls(id) ON DELETE CASCADE
);

-- Execution approvals
CREATE TABLE IF NOT EXISTS execution_approvals (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    tool_call_id TEXT NOT NULL,
    command_hash TEXT NOT NULL,
    command TEXT NOT NULL,
    shell TEXT NOT NULL,
    cwd TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL, -- 'pending', 'approved_once', 'approved_session', 'denied', 'expired'
    decided_by TEXT,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Session permissions
CREATE TABLE IF NOT EXISTS session_permissions (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    scope TEXT NOT NULL, -- 'read_only', 'workspace_modify', 'all_safe'
    tool_name TEXT,
    cwd TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Providers
CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL, -- 'openai_compatible', 'ollama', 'anthropic', 'gemini', 'lm_studio'
    base_url TEXT NOT NULL,
    api_key_encrypted TEXT,
    auth_type TEXT DEFAULT 'bearer',
    custom_headers_json TEXT DEFAULT '{}',
    models_endpoint TEXT DEFAULT '/models',
    chat_endpoint TEXT DEFAULT '/chat/completions',
    is_enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Provider Models
CREATE TABLE IF NOT EXISTS provider_models (
    id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    display_name TEXT,
    context_length INTEGER DEFAULT 8192,
    supports_tools INTEGER DEFAULT 1,
    supports_vision INTEGER DEFAULT 0,
    is_local INTEGER DEFAULT 0,
    is_enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE
);

-- Agent Profiles
CREATE TABLE IF NOT EXISTS agent_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    system_instructions TEXT NOT NULL,
    preferred_tools_json TEXT DEFAULT '[]',
    default_risk_mode TEXT DEFAULT 'allow_safe',
    is_builtin INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- System Prompts
CREATE TABLE IF NOT EXISTS system_prompts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    is_global INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Project Workspaces
CREATE TABLE IF NOT EXISTS project_workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Memory Facts
CREATE TABLE IF NOT EXISTS memory_facts (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    category TEXT NOT NULL, -- 'user_preference', 'project_detail', 'environment', 'instruction'
    content TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Conversation Summaries
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL UNIQUE,
    summary_text TEXT NOT NULL,
    last_message_id TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Attachments
CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    message_id TEXT,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Application Settings
CREATE TABLE IF NOT EXISTS application_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Skills (Slash commands & specialized agent capabilities)
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    command TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    icon TEXT DEFAULT 'sparkles',
    color TEXT DEFAULT 'indigo',
    is_builtin INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

-- MCP Servers (Model Context Protocol external tool providers)
CREATE TABLE IF NOT EXISTS mcp_servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    transport_type TEXT NOT NULL, -- 'stdio' or 'sse'
    command TEXT,
    args_json TEXT DEFAULT '[]',
    env_json TEXT DEFAULT '{}',
    url TEXT,
    is_enabled INTEGER DEFAULT 1,
    status TEXT DEFAULT 'disconnected',
    last_error TEXT,
    tools_count INTEGER DEFAULT 0,
    tools_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Indexes for lightning fast queries
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_conv ON tool_calls(conversation_id);
CREATE INDEX IF NOT EXISTS idx_approvals_conv ON execution_approvals(conversation_id);
CREATE INDEX IF NOT EXISTS idx_provider_models ON provider_models(provider_id);
CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_facts(category);
"""

# FTS5 Full Text Search table and triggers for messages
CREATE_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    message_id UNINDEXED,
    conversation_id UNINDEXED,
    content
);

-- Triggers to keep FTS in sync with messages table
CREATE TRIGGER IF NOT EXISTS trg_messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(message_id, conversation_id, content)
    VALUES (new.id, new.conversation_id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS trg_messages_ad AFTER DELETE ON messages BEGIN
    DELETE FROM messages_fts WHERE message_id = old.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_messages_au AFTER UPDATE ON messages BEGIN
    DELETE FROM messages_fts WHERE message_id = old.id;
    INSERT INTO messages_fts(message_id, conversation_id, content)
    VALUES (new.id, new.conversation_id, new.content);
END;
"""

async def init_db():
    """
    Initializes database schema and seeds initial agent profiles, default prompt,
    local providers and application settings if empty.
    """
    logger.info("Initializing SQLite database and applying schema...")
    async with get_db() as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.executescript(CREATE_FTS_SQL)
        await db.commit()

        try:
            await db.execute("ALTER TABLE mcp_servers ADD COLUMN tools_json TEXT DEFAULT '[]';")
            await db.commit()
        except Exception:
            pass
        
        # Check if agent profiles exist
        cursor = await db.execute("SELECT COUNT(*) FROM agent_profiles;")
        (count,) = await cursor.fetchone()
        
        now = datetime.utcnow().isoformat() + "Z"
        
        if count == 0:
            logger.info("Seeding builtin agent profiles...")
            profiles = [
                (
                    "general-assistant",
                    "General Assistant",
                    "Helpful, versatile AI workstation assistant for general queries, writing, and problem solving.",
                    "You are NOVA, a versatile and intelligent AI desktop assistant. Assist the user with clear explanations, structured advice, and tool executions when requested.",
                    json.dumps(["get_current_datetime", "calculate", "list_directory", "read_file"]),
                    "allow_safe",
                    1,
                    now
                ),
                (
                    "software-developer",
                    "Software Developer",
                    "Full-stack development specialist proficient in Python, TypeScript, modern frameworks, and debugging.",
                    "You are NOVA Developer, an expert software engineer. You analyze codebases, run tests, diagnose errors, apply clean patches, and build robust software iteratively.",
                    json.dumps(["run_python", "run_script", "inspect_project", "list_project_files", "search_code", "read_source_file", "apply_file_patch", "run_tests"]),
                    "allow_safe",
                    1,
                    now
                ),
                (
                    "senior-python-engineer",
                    "Senior Python Engineer",
                    "Specialized in modern asynchronous Python, FastAPI, type annotations, and performance optimization.",
                    "You are a Senior Python Engineer. Write idiomatic, PEP 8 compliant, type-hinted, high-performance Python. Debug tracebacks, analyze dependencies, and write unit tests.",
                    json.dumps(["run_python", "run_tests", "inspect_project", "list_directory", "read_file", "edit_file"]),
                    "allow_safe",
                    1,
                    now
                ),
                (
                    "windows-admin",
                    "Windows System Administrator",
                    "Expert in Windows PowerShell, system diagnostics, services, process management, and troubleshooting.",
                    "You are a Windows System Administration Agent. Help inspect system health, manage services, diagnose resource bottlenecks, and execute safe diagnostic PowerShell commands.",
                    json.dumps(["execute_powershell", "get_system_information", "get_os_information", "get_running_processes", "inspect_services", "inspect_environment", "inspect_disk_usage"]),
                    "allow_safe",
                    1,
                    now
                ),
                (
                    "research-agent",
                    "Research Agent",
                    "Synthesizes information, explores project documentation, organizes insights, and maintains memory facts.",
                    "You are NOVA Research Agent. Read files, organize structured notes, retrieve past conversation insights, and extract persistent knowledge facts.",
                    json.dumps(["search_files", "read_file", "search_conversation_history", "retrieve_relevant_memory", "save_conversation_memory"]),
                    "allow_safe",
                    1,
                    now
                ),
                (
                    "devops-engineer",
                    "DevOps Engineer",
                    "Automation, environment setup, dependencies, process monitoring, and build pipelines.",
                    "You are a DevOps and Infrastructure Specialist. Help configure environments, inspect ports, execute build tools, and troubleshoot execution logs.",
                    json.dumps(["execute_powershell", "execute_cmd", "inspect_network_configuration", "run_script", "inspect_environment"]),
                    "allow_safe",
                    1,
                    now
                )
            ]
            await db.executemany(
                "INSERT INTO agent_profiles (id, name, description, system_instructions, preferred_tools_json, default_risk_mode, is_builtin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                profiles
            )
            await db.commit()
            
        # Check system prompt
        cursor = await db.execute("SELECT COUNT(*) FROM system_prompts;")
        (prompt_count,) = await cursor.fetchone()
        if prompt_count == 0:
            logger.info("Seeding default system prompt...")
            default_prompt = (
                "default-global-prompt",
                "NOVA Core Operational Directive",
                "You are NOVA, an advanced local AI agent running natively on the user's computer. Always match the user's communication language: reply 100% in natural Persian if prompted in Persian, in English if in English, etc. When building projects, applications, or codebases, create a dedicated subfolder inside the scratch workspace to keep files clean and organized. For simple one-off tasks, create files directly in scratch.",
                1,
                1,
                now
            )
            await db.execute(
                "INSERT INTO system_prompts (id, name, content, is_global, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?);",
                default_prompt
            )
            await db.commit()
        else:
            updated_prompt_text = "You are NOVA, an advanced local AI agent running natively on the user's computer. Always match the user's communication language: reply 100% in natural Persian if prompted in Persian, in English if in English, etc. When building projects, applications, or codebases, create a dedicated subfolder inside the scratch workspace to keep files clean and organized. For simple one-off tasks, create files directly in scratch."
            await db.execute(
                "UPDATE system_prompts SET content = ? WHERE id = 'default-global-prompt';",
                (updated_prompt_text,)
            )
            await db.commit()

        # Providers start completely empty on initial setup
        # Users configure their own provider during the first-time onboarding modal or in Settings
        logger.info("Database initialized with 0 default providers (clean initial setup).")

        # Seed or update default scratch workspace
        cursor = await db.execute("SELECT COUNT(*) FROM project_workspaces;")
        (ws_count,) = await cursor.fetchone()
        if ws_count == 0:
            ws = (
                "default-workspace",
                "NOVA Scratch Workspace",
                str(settings.DEFAULT_WORKSPACE),
                "Default project scratch workspace for generated code and files",
                1,
                now
            )
            await db.execute(
                "INSERT INTO project_workspaces (id, name, path, description, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?);",
                ws
            )
            await db.commit()
        else:
            await db.execute(
                "UPDATE project_workspaces SET path = ?, name = 'NOVA Scratch Workspace' WHERE id = 'default-workspace';",
                (str(settings.DEFAULT_WORKSPACE),)
            )
            await db.commit()

        # Seed default skills
        cursor = await db.execute("SELECT COUNT(*) FROM skills;")
        (skills_count,) = await cursor.fetchone()
        if skills_count == 0:
            logger.info("Seeding builtin agent skills...")
            builtin_skills = [
                (
                    "skill-research",
                    "Deep Research",
                    "/research",
                    "Multi-step web exploration & comprehensive codebase synthesis",
                    "Activate Deep Research mode: Use search and web tools iteratively to verify facts, cross-reference multiple sources, inspect source files, and produce an exhaustive, analytical report.",
                    "search",
                    "emerald",
                    1,
                    now
                ),
                (
                    "skill-think",
                    "Deep Think",
                    "/think",
                    "Extended chain-of-thought, system architecture & deep reflection",
                    "Activate Deep Think mode: Engage in meticulous, step-by-step reasoning. Break down edge cases, evaluate trade-offs, architect robust solutions, and challenge assumptions before reaching conclusions.",
                    "brain",
                    "amber",
                    1,
                    now
                ),
                (
                    "skill-web",
                    "Web Search",
                    "/web",
                    "Real-time live internet information gathering & retrieval",
                    "Activate Web Search mode: Prioritize DuckDuckGo and live web search. Read relevant web pages thoroughly, extract fresh information, and provide well-cited up-to-date answers.",
                    "globe",
                    "blue",
                    1,
                    now
                ),
                (
                    "skill-code",
                    "Code Architect",
                    "/code",
                    "Production software engineering, refactoring, and clean code review",
                    "Activate Code Architect mode: Write clean, type-hinted, maintainable code following solid architectural principles. Inspect dependencies, handle edge cases, and ensure high testability.",
                    "code",
                    "purple",
                    1,
                    now
                ),
                (
                    "skill-debug",
                    "System Debugger",
                    "/debug",
                    "Root cause analysis, stack trace diagnosis & automated bug fixing",
                    "Activate System Debugger mode: Carefully read logs, inspect exception tracebacks, reproduce bugs, isolate root causes, and apply exact fixes without regressions.",
                    "bug",
                    "rose",
                    1,
                    now
                ),
                (
                    "skill-terminal",
                    "Terminal Commander",
                    "/terminal",
                    "Native PowerShell, CMD, Bash, and Zsh command line automation across Windows, macOS, and Linux",
                    "Activate Terminal Commander mode: Assist with precise, safe, non-interactive commands adapted to the active OS (PowerShell/CMD on Windows, Bash/Zsh on Linux and macOS). Explain commands before execution and verify exit codes.",
                    "terminal",
                    "cyan",
                    1,
                    now
                ),
                (
                    "skill-rss",
                    "RSS Feeds Explorer",
                    "/rss",
                    "Browse curated country & topic RSS feed trees and fetch live news/articles",
                    "Activate RSS Feeds Explorer mode: Follow NOVA's hierarchical RSS Tree workflow end-to-end to deliver verified live news and articles: 1) Inspect the target branch with get_rss_category_feeds(category=..., filter=...) (e.g. category='News', filter='world' for World News) or list_rss_categories, 2) Unless the user ONLY wanted raw feed URLs, NEVER stop at directory links: immediately call fetch_rss_feed(category=..., feed_filter=..., query=..., max_items=20) or fetch_rss_feed(url=...) to retrieve live articles, 3) Synthesize the headlines, dates, summaries, and source links thoroughly in the user's language, and 4) NEVER invoke shell/PowerShell commands to scrape external websites.",
                    "rss",
                    "orange",
                    1,
                    now
                )
            ]
            await db.executemany(
                "INSERT INTO skills (id, name, command, description, system_prompt, icon, color, is_builtin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                builtin_skills
            )
            await db.commit()
        else:
            cursor = await db.execute("SELECT COUNT(*) FROM skills WHERE command = '/rss';")
            (rss_exists,) = await cursor.fetchone()
            if rss_exists == 0:
                await db.execute(
                    "INSERT INTO skills (id, name, command, description, system_prompt, icon, color, is_builtin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                    (
                        "skill-rss",
                        "RSS Feeds Explorer",
                        "/rss",
                        "Browse curated country & topic RSS feed trees and fetch live news/articles",
                        "Activate RSS Feeds Explorer mode: Follow NOVA's hierarchical RSS Tree workflow end-to-end to deliver verified live news and articles: 1) Inspect the target branch with get_rss_category_feeds(category=..., filter=...) (e.g. category='News', filter='world' for World News) or list_rss_categories, 2) Unless the user ONLY wanted raw feed URLs, NEVER stop at directory links: immediately call fetch_rss_feed(category=..., feed_filter=..., query=..., max_items=20) or fetch_rss_feed(url=...) to retrieve live articles, 3) Synthesize the headlines, dates, summaries, and source links thoroughly in the user's language, and 4) NEVER invoke shell/PowerShell commands to scrape external websites.",
                        "rss",
                        "orange",
                        1,
                        now
                    )
                )
                await db.commit()

        # Built-in HTML/image styling lives in core PromptEngine instructions, not user-visible Memory
        await db.execute(
            "DELETE FROM memory_facts WHERE id = 'mem-global-chat-image-display' OR content LIKE '%HTML <img> tags with direct URLs%';"
        )
        await db.commit()

    logger.info("Database initialization and migrations completed successfully.")
