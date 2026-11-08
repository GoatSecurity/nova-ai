<div align="center">

<img src="frontend/public/logo.png" alt="NOVA Logo" width="140" />

# NOVA

### Your AI. Your Machine. Your Rules.

**A local-first AI workstation for Windows, macOS, and Linux. Run open-source models on your own hardware, connect the AI providers you choose, research the web, work with files, and automate real tasks from one unified workspace.**

<br />

> **Stop renting every AI interaction. Run your own models with NOVA.**
>
> Use compatible local models through Ollama or LM Studio with zero per-request cloud API charges. Connect cloud providers only when you choose to.

<br />

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-0078D6?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Local AI](https://img.shields.io/badge/local%20AI-Ollama%20%7C%20LM%20Studio-16A34A?style=for-the-badge)
![MCP](https://img.shields.io/badge/integrations-MCP-6366F1?style=for-the-badge)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
[![Download Windows x64 Installer](https://img.shields.io/badge/Download-Windows%20x64%20Installer-0ea5e9?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/GoatSecurity/nova-ai/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

<br />

**[GitHub Repository](https://github.com/GoatSecurity/nova-ai) · [Download Windows Installer](https://github.com/GoatSecurity/nova-ai/releases/latest) · [Explore the Features](#-what-you-can-do-with-nova) · [Run Local AI](#-run-local-ai-without-per-request-api-costs) · [Installation](#-get-started) · [Security](#-privacy--security) · [FAQ](#-frequently-asked-questions)**

<br />

<img src="screenshots/03_main_workstation.png" alt="NOVA AI workstation interface" width="100%" />

<sub>Your models. Your tools. Your workflow — in one place.</sub>

</div>

---

## Meet NOVA

NOVA brings AI chat, agent workflows, local and cloud models, web research, terminal access, file operations, and extensible tools together in one locally hosted workstation. Built around a lightweight Python/FastAPI core, NOVA runs across Windows, macOS, and Linux.

Instead of being locked into a single AI provider or subscription, you choose how NOVA operates:

- **Run local models** through [Ollama](https://ollama.com/) or [LM Studio](https://lmstudio.ai/).
- **Connect cloud models** with your own API keys when you need frontier cloud capabilities.
- **Give your agent tools** to inspect project files, execute commands, and complete multi-step tasks.
- **Search the web** via built-in DuckDuckGo integration when real-time online information is needed.
- **Extend the workspace** with Model Context Protocol (MCP) servers and custom Agent Skills.
- **Stay in control** with configurable approval policies for command execution.

NOVA is engineered for developers, researchers, makers, and power users who demand full control over their models, data paths, and local tooling.

---

## 🖥️ Platform Support

NOVA is built on a Python/FastAPI backend with a modern web interface, running natively across all major desktop operating systems. Windows serves as the primary target for deep OS-level integrations:

| Platform | Support Level | Platform-Specific Notes |
|---|---|---|
| **Windows 10 / 11 (x64)** | Primary Platform | Dedicated standalone desktop installer ([`nova-windows-64-installer.exe`](https://github.com/GoatSecurity/nova-ai/releases/latest)) with zero-setup desktop app, plus full PowerShell/CMD & Windows DPAPI credential encryption. |
| **macOS** | Supported (Core & POSIX) | Runs the full FastAPI core, local/cloud models, MCP, and native `zsh`/`bash` shell integrations. |
| **Linux** | Supported (Core & POSIX) | Runs the full FastAPI core, local/cloud models, MCP, and native `bash` shell integrations. |

---

## ✨ What You Can Do with NOVA

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>🧠 Local & Cloud AI</h3>
      Seamlessly switch between local model runtimes and cloud APIs. Use your own endpoints, custom headers, and local weights.
    </td>
    <td width="50%" valign="top">
      <h3>🤖 Agent Workflows</h3>
      Assign NOVA a high-level goal. Let it break the task into steps, invoke tools, inspect outputs, and report back upon completion.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>💻 Desktop & Terminal Automation</h3>
      Execute PowerShell, CMD, or POSIX shell commands directly from agent workflows. Read and modify files safely within workspace boundaries.
    </td>
    <td width="50%" valign="top">
      <h3>🌐 Web Research</h3>
      Retrieve live online information using built-in DuckDuckGo search to ground agent responses in current documentation and facts.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🔌 MCP Integrations</h3>
      Connect remote MCP servers or spawn local <code>stdio</code> MCP processes (via <code>npx</code>, <code>uvx</code>, or <code>python</code>) to expand your agent's toolset.
    </td>
    <td width="50%" valign="top">
      <h3>🧩 Custom Agent Skills</h3>
      Package recurring prompts and tool workflows into reusable Markdown manifests (<code>SKILL.md</code>) triggered via slash commands.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>📊 Workstation Controls</h3>
      Monitor real-time system telemetry (CPU, RAM, network), manage workspaces, and inspect active agent processes from one dashboard.
    </td>
    <td width="50%" valign="top">
      <h3>🛡️ User-Governed Execution</h3>
      Set strict execution policies (<code>ask_always</code>, <code>allow_safe</code>, or <code>autonomous</code>) so no critical system action happens without your consent.
    </td>
  </tr>
</table>

---

## 🖥️ Inside the Workstation

NOVA's interface is built around getting real work done—not just scrolling through chat history.

| Workspace Area | Purpose |
|---|---|
| **Agent Workspace** | Chat with models, track multi-step task progress, and inspect live tool execution logs. |
| **Provider Setup** | Configure Ollama, LM Studio, OpenAI, Anthropic, Gemini, DeepSeek, Groq, or custom endpoints. |
| **MCP Manager** | Connect, authenticate, and inspect tools exposed by local or remote MCP servers. |
| **Skills Catalog** | Browse built-in slash commands or load your own custom `SKILL.md` workflows. |
| **Control Center** | Monitor hardware telemetry, configure workspace boundaries, and set command approval rules. |

<div align="center">
  <img src="screenshots/02_onboarding_provider.png" alt="NOVA provider configuration" width="82%" />
  <br />
  <sub>Connect a local runtime or configure your preferred cloud provider.</sub>
</div>

<br />

<div align="center">
  <img src="screenshots/04_mcp_servers.png" alt="NOVA MCP server management" width="82%" />
  <br />
  <sub>Extend NOVA with compatible MCP tools.</sub>
</div>

<br />

<div align="center">
  <img src="screenshots/05_skills_catalog.png" alt="NOVA Agent Skills catalog" width="82%" />
  <br />
  <sub>Use built-in skills or build your own workflows.</sub>
</div>

---

## 🦙 Run Local AI Without Per-Request API Costs

NOVA connects directly to local inference engines like [Ollama](https://ollama.com/) and [LM Studio](https://lmstudio.ai/). Download an open-weights model, run it on your hardware, and select it inside NOVA.

```text
Your Prompt
    │
    ▼
┌───────────────────────────────┐
│             NOVA              │
│  Chat · Agent · Tools · Memory│
└───────────────────────────────┘
    │                       │
    ▼                       ▼
┌──────────────────┐  ┌──────────────────┐
│      Ollama      │  │    LM Studio     │
│  Local Endpoint  │  │  Local Endpoint  │
└──────────────────┘  └──────────────────┘
    │                       │
    └───────────┬───────────┘
                ▼
       Your Local Hardware

```

### Quick Setup with Ollama

1. Install [Ollama](https://ollama.com/).
2. Pull a model suited to your hardware:
```bash
ollama pull llama3.2

```


3. Ensure the Ollama server is running (`http://127.0.0.1:11434`).
4. Open NOVA, select the **Ollama** preset, choose your model, and start working.

### Quick Setup with LM Studio

1. Install [LM Studio](https://lmstudio.ai/) and download a compatible GGUF model.
2. Start the local OpenAI-compatible server inside LM Studio (`http://127.0.0.1:1234/v1`).
3. In NOVA, select the **LM Studio** preset, save the connection, and pick your loaded model.

---

## 🔗 Supported Model Providers

* **Local Runtimes:** Ollama, LM Studio, and any custom OpenAI-compatible local server.
* **Cloud Providers:** OpenAI, Anthropic Claude, Google Gemini, DeepSeek, and Groq (Bring Your Own API Key).

---

## 💻 Terminal Automation & Approval Modes

NOVA bridges AI reasoning with OS-level execution:

* **Shell Execution:** PowerShell and CMD on Windows; `bash` and `zsh` on Linux/macOS.
* **File System Operations:** Read, write, create, move, and inspect files strictly within your designated workspace directory.
* **Process Management:** Inspect `stdout`, `stderr`, and exit codes in real time, or terminate hanging processes.

### Execution Policies

Control exactly how much autonomy NOVA has over your terminal:

* **`allow_safe`** — Automatically runs read-only and low-risk inspections while prompting you before modifying files or running system commands.
* **`ask_always`** — Requires explicit user approval before executing any command.
* **`autonomous`** — Grants full execution permissions within the active workspace boundaries. Use with caution.

---

## 🔌 Model Context Protocol (MCP)

Extend NOVA's capabilities by connecting external tools via MCP:

* **Local Process (`stdio`):** Spawn local MCP servers using `npx`, `uvx`, or `python` with custom arguments and environment variables.
* **Remote Server:** Connect to HTTP/SSE MCP endpoints with custom authentication headers.

To add a server, navigate to **Settings → MCP Servers & External Tools → Add MCP Server**.

---

## 🧩 Agent Skills

Package complex instructions and tool rules into reusable skills located at `skills/<skill-name>/SKILL.md`.

| Built-in Skill | Purpose |
| --- | --- |
| `/research` | Multi-step web research and synthesis. |
| `/code` | Codebase architecture analysis, refactoring, and implementation. |
| `/debug` | Root-cause analysis for stack traces and terminal errors. |
| `/terminal` | Guided command-line execution and automation. |
| `/web` | Focused live web queries via DuckDuckGo. |
| `/rss` | Progressive RSS feed tree explorer & live news aggregator (~780 curated feeds). |

### Creating a Custom Skill

Create `skills/myskill/SKILL.md` with the following frontmatter:

```markdown
---
name: My Custom Skill
command: /myskill
description: Automates my specific recurring workflow
icon: terminal
color: emerald
---

Define the step-by-step instructions, permitted tools, and safety constraints here.

```

---

## 🔒 Privacy & Security

* **Local-First Storage:** All conversation history, workspace configs, and settings are stored locally in `data/nova.db` (SQLite).
* **Credential Protection:** On Windows, API keys are encrypted at rest using Windows DPAPI tied to your user security context.
* **Zero Telemetry Lock-in:** Prompts sent to local models never leave your machine. External network calls only occur when you explicitly invoke web search, remote MCP servers, or cloud LLM APIs.

---

## ⚡ Get Started

### Option 1: Install Directly on Windows (Recommended — Zero Setup)

You can install NOVA directly on **Windows 10 / 11 (64-bit)** without installing Python, Git, or Node.js:

| Package | Architecture | Size | SHA-256 | Download |
|---|---|---|---|---|
| `nova-windows-64-installer.exe` | Windows 64-bit (`x64`) | `65.03 MB` | `62615c3debbcac646b9447b82fb8f2561fc30be0e8a2c4e578239f1fa6cdd424` | **[Download Latest Release](https://github.com/GoatSecurity/nova-ai/releases/download/v1.0.0/nova-windows-64-installer.exe)** |

1. Download **`nova-windows-64-installer.exe`** from **[GitHub Releases](https://github.com/GoatSecurity/nova-ai/releases/latest)** and double-click to launch the setup wizard.
2. Choose your installation directory (defaults to `%LOCALAPPDATA%\Programs\NOVA` — no Administrator rights required), select **Desktop Shortcut** / **Launch After Install**, and click **Install NOVA**.
3. Open **NOVA** from your Desktop shortcut or Start Menu. NOVA launches inside a native desktop workstation powered by a background engine on a random free localhost port (no extra browser windows opened).
4. **Clean Uninstall:** Uninstall anytime via **Windows Settings → Apps → Installed Apps (`NOVA`)** or `uninstall.exe` to cleanly remove the application, shortcuts, logs, and local database.

*(A 32-bit Windows build will be added in a future release.)*

---

### Option 2: Run from Source (Windows, macOS & Linux)

#### Prerequisites

* **Python:** 3.11 or higher
* **Git**
* **Local AI Runtime (Optional):** [Ollama](https://ollama.com/) or [LM Studio](https://lmstudio.ai/)

#### 1. Clone the Repository

```bash
git clone https://github.com/GoatSecurity/nova-ai.git
cd nova-ai
```

#### 2. Run on Windows (One-Click Launcher)

Run the included batch or PowerShell launcher to start NOVA immediately:

```powershell
.\start.bat
```

*(Or run `.\start.ps1` in PowerShell, or universal `python run.py`. To stop the server, press `Ctrl+C` or run `.\stop.bat`.)*

#### 3. Run on macOS & Linux (One-Command Launcher)

Make the scripts executable once and launch NOVA (auto-creates `.venv`, installs dependencies, opens your browser):

```bash
chmod +x start.sh stop.sh
./start.sh
```

*(Or run universally on any OS with `pip install -r requirements.txt && python run.py`. To stop, press `Ctrl+C` or run `./stop.sh`.)*

#### 4. Launch the Interface

Open your browser and navigate to:

```text
http://127.0.0.1:46815
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Enter` | Send prompt |
| `Shift + Enter` | Insert new line |
| `/` | Open Agent Skills selector |
| `Ctrl + K` | Search conversations and history |
| `Esc` | Close active modal or menu |
| `Right-Click` (on chat) | Rename, pin, export, or delete conversation |

---

## ❓ Frequently Asked Questions

**Do I need Python installed to use the Windows installer?**
No. [`nova-windows-64-installer.exe`](https://github.com/GoatSecurity/nova-ai/releases/latest) bundles the entire Python runtime, NOVA backend/frontend, and desktop workstation shell.

**Where are my conversations, models, and encrypted API keys stored?**
When installed with the Windows desktop installer, user data is stored locally under `%LOCALAPPDATA%\NOVA\data\nova.db`. When running from source, it is stored in `data/nova.db` inside the project directory. On Windows, API keys are encrypted at rest via Windows DPAPI.

**Does NOVA send data to external servers automatically?**
No. Prompts sent to local providers (Ollama, LM Studio, or local OpenAI-compatible servers) remain completely on your machine. External requests only happen when you explicitly configure a cloud API key, enable live Web Search / RSS tools, or connect a remote MCP server.

---

## 🧑‍🚀 Contributing

Contributions, bug reports, and custom skills are welcome!

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`) and open a Pull Request.

Please ensure all logs or screenshots shared in Issues are stripped of personal API keys and sensitive paths.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for full details.

---

## Make Your Machine Your AI Workspace.

**NOVA — Your AI. Your Machine. Your Rules.**

**[⬆ Back to the top](#nova)**
