# Local AI Coding Agent

A fully local AI agent powered by Ollama and open-source LLMs. It can reason, call tools, edit code, run checks, use the desktop, and expose a Web UI for interactive work.

## Features

- ReAct loop for iterative reasoning and tool use
- Rich CLI with real-time streaming
- Web UI with WebSocket streaming and a dark interface
- 18 built-in tools: shell, file operations, code runner, computer use, web search, and git
- Memory: short-term context plus long-term SQLite history
- Safety gate for dangerous or sensitive actions
- Privacy boundary for secrets, private keys, `.env` files, and outbound requests
- Cross-platform shell support: PowerShell on Windows, bash on Linux/macOS

## Quick Start

### 1. Install Ollama

Linux/macOS:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Windows: download and install Ollama from https://ollama.com.

### 2. Pull a Model

```bash
# Default orchestrator for research, planning, and coordination
ollama pull qwen3:8b

# Optional coding model
ollama pull qwen2.5-coder:7b

# Stronger coding model
ollama pull qwen2.5-coder:14b
```

### 3. Install Dependencies

```bash
git clone <repo-url>
cd local-agent
python setup.py

# Or install manually:
pip install -r requirements.txt
```

### 4. Run

```bash
# Start Ollama if it is not already running
ollama serve

# Interactive CLI
python main.py

# One-shot task
python main.py "read main.py and explain it"

# Default idle task: learn system design, conventions, and DevOps practices for future projects
python main.py --default-task

# Web UI
python main.py --web
# Open http://localhost:8000
```

## CLI Usage

```bash
# Interactive mode
python main.py

# One-shot with a specific model
python main.py "research this product idea and draft an MVP plan" --model qwen3:8b

# Auto-confirm actions, use carefully
python main.py --yes "clean cache and rebuild"

# Show chat history
python main.py history

# List installed Ollama models
python main.py models
```

### Interactive Commands

| Command | Description |
|---|---|
| `/exit` | Exit |
| `/history` | Show recent history |
| `/clear` | Clear memory context |
| `/models` | List models |
| `/default` | Run the default idle task |

Press Enter on an empty prompt to run the default idle task.

## Web UI

```bash
python main.py --web --port 8000
```

Open http://localhost:8000.

Web UI features:

- Chat interface with WebSocket streaming
- Step-by-step agent traces, expandable in the UI
- System status panel for CPU, RAM, GPU, and temperature metrics
- Instant response mode for direct no-tool replies with an optional faster model
- Auto-confirm toggle
- Runtime model selection
- Memory clearing
- Run Default button for system design, web/app design, coding conventions, and DevOps learning

## System Status

The Web UI polls this endpoint every few seconds:

```bash
curl http://localhost:8000/api/system/status
```

It returns best-effort local performance metrics:

- CPU utilization and load average
- RAM and swap usage
- GPU utilization, memory, power, and temperature when `nvidia-smi` is available
- Apple/integrated GPU device information when exposed by the OS
- Temperature sensors when exposed by `psutil`; on macOS, `osx-cpu-temp` can provide CPU temperature
- Battery status when available

Install dependencies for richer metrics:

```bash
pip install -r requirements.txt
```

GPU utilization and temperature are platform-dependent. If the OS or driver does not expose a metric, the UI shows `N/A` instead of failing.

## Instant Response Mode

Qwen reasoning models can be slower in full Agent mode because the agent uses a ReAct loop and tool routing. The Web UI includes an **Instant response** toggle for quick no-tool replies.

Instant mode:

- sends the prompt directly to Ollama
- skips the tool loop
- uses a shorter context window
- does not expose reasoning
- can use a separate faster model

Configure a fast model:

```bash
export AGENT_FAST_MODEL="qwen2.5:3b"
python main.py --web --port 8000
```

You can also pick a fast model from the Web UI dropdown. Keep Agent mode for tasks that need files, shell commands, browser/computer use, web search, or repo changes.

## Task and Confirmation API

The backend also exposes REST endpoints so other apps can submit tasks and respond to confirmation prompts.

### 1. Create a Task

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Research product idea X, evaluate the path to market, plan the MVP, and implement it",
    "auto_confirm": false,
    "max_steps": 25
  }'
```

If `"task": ""`, the backend runs the default idle task.

Example response:

```json
{
  "task_id": "...",
  "status": "queued",
  "pending_confirmation": null,
  "events": []
}
```

### 2. Check Task Status

```bash
curl http://localhost:8000/api/tasks/<task_id>
```

When the agent needs confirmation, the response includes:

```json
{
  "status": "waiting_confirmation",
  "pending_confirmation": {
    "confirmation_id": "...",
    "tool": "web_search",
    "prompt": "..."
  }
}
```

### 3. Confirm or Decline

```bash
curl -X POST http://localhost:8000/api/tasks/<task_id>/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "confirmation_id": "<confirmation_id>",
    "confirmed": true
  }'
```

To decline, send `"confirmed": false`.

## Telegram Notifications

The Web API can send task status updates to Telegram. This is optional and is enabled when both environment variables are set:

```bash
export TELEGRAM_BOT_TOKEN="<bot-token-from-botfather>"
export TELEGRAM_CHAT_ID="<your-chat-id>"
python main.py --web --port 8000
```

How to set it up:

1. Create a Telegram bot with `@BotFather` and copy the bot token.
2. Send any message to your bot from the Telegram app.
3. Get your chat id:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates"
```

4. Set `TELEGRAM_CHAT_ID` to the `message.chat.id` value.

Check notification configuration:

```bash
curl http://localhost:8000/api/notifications
```

Send a test Telegram notification:

```bash
curl -X POST http://localhost:8000/api/notifications/telegram/test
```

Send the current status of a task to Telegram:

```bash
curl -X POST http://localhost:8000/api/tasks/<task_id>/notify \
  -H "Content-Type: application/json" \
  -d '{"channel": "telegram"}'
```

When configured, REST tasks automatically notify Telegram when they are queued, started, waiting for confirmation, resumed, completed, or failed.

## Operating Workflow

The agent is designed to:

- Receive tasks through CLI, WebSocket, or `POST /api/tasks`.
- For product ideas, research the market path before implementation: target users, pain points, distribution channels, risks, and MVP scope.
- Build feature by feature with clear completion criteria.
- In git repositories, inspect `git status`, use focused changes, run relevant checks, and summarize a PR-ready diff.
- Never merge or delete branches without explicit approval.
- Ask for confirmation before outbound requests, sensitive file access, risky commands, or high-impact changes.

Expected tool roles:

- Research: browser/ChatGPT/Gemini/Chrome/Edge adapters or `web_search`, with confirmation for every outbound query.
- Implementation: local file tools, shell, code runners, and optional adapters for Codex/Claude/Gemini/Cursor.
- Delivery: git status, diff, log, PR-ready summaries, and safe merge steps after confirmation.

This repository currently includes the core local tools and task/confirmation API. Direct integrations with ChatGPT, Gemini, Chrome, Edge, Codex, Claude, or Cursor require additional adapters.

## Tools

| Tool | Description | Confirmation |
|---|---|---|
| `run_shell` | Run bash/PowerShell commands | Required for risky patterns |
| `read_file` | Read a file with line numbers | Required for sensitive paths |
| `write_file` | Write or overwrite a file | Always |
| `patch_file` | Replace a unique string in a file | Required for sensitive paths |
| `list_dir` | List directory contents | Required for sensitive paths |
| `search_files` | Search files recursively | Required for sensitive paths |
| `run_python` | Run a Python snippet | Required for risky/outbound patterns |
| `run_nodejs` | Run a Node.js snippet | Required for risky/outbound patterns |
| `computer_observe` | Read the active app/window accessibility tree before acting | No |
| `computer_click` | Click screen coordinates | Always unless auto-confirm is enabled |
| `computer_type` | Type text into the active app/window | Always unless auto-confirm is enabled |
| `computer_press` | Press a key in the active app/window | Always unless auto-confirm is enabled |
| `computer_hotkey` | Press a key combination such as `command+l` or `ctrl+c` | Always unless auto-confirm is enabled |
| `computer_screenshot` | Capture the current desktop | No |
| `computer_position` | Get the current mouse position when supported | No |
| `web_search` | Search DuckDuckGo; query leaves the machine | Always |
| `git_status` | Show git status | No |
| `git_diff` | Show git diff | No |
| `git_log` | Show recent commits | No |

## Privacy Boundary

The agent runs locally, but some tools can still leak data if used carelessly. The current boundary:

- Blocks private key and secret-store paths such as `.ssh/id_*`, `.gnupg/`, macOS Keychains, and Windows Credentials.
- Requires confirmation for sensitive paths such as `.env`, `.npmrc`, `.pypirc`, `.aws/`, `.azure/`, Docker config, and files named `secret*` or `credentials*`.
- Requires confirmation for every `web_search` query because it leaves the machine.
- Requires confirmation when shell/code appears to make outbound requests with tools or libraries such as `curl`, `wget`, `scp`, `rsync`, `requests`, `httpx`, `fetch`, or `axios`.
- Blocks sending secret-like text to external tools.
- Refuses actions that need confirmation when there is no confirmation channel.

This is an application-level guardrail, not an operating-system sandbox. For sensitive work, use a dedicated workspace, a low-privilege account, and controlled outbound tools.

## Add a New Tool

1. Create `agent/tools/my_tool.py`:

```python
async def my_tool(arg1: str, arg2: int = 5) -> str:
    # Your tool logic here.
    return "result"
```

2. Register it in `agent/tools/registry.py`:

```python
from agent.tools.my_tool import my_tool

TOOLS["my_tool"] = {
    "fn": my_tool,
    "description": "Short description for the LLM.",
    "args": {"arg1": "string", "arg2": "int (optional)"},
    "dangerous": False,
}
```

The agent will then be able to call the tool.

## Configuration

Edit `config/default.yaml` or use environment variables:

```bash
AGENT_MODEL=qwen3:8b
AGENT_FAST_MODEL=qwen2.5:3b
OLLAMA_URL=http://localhost:11434
AGENT_DEFAULT_TASK="Learn one system design/conventions/DevOps topic and summarize how to apply it to a project"
TELEGRAM_BOT_TOKEN="<bot-token-from-botfather>"
TELEGRAM_CHAT_ID="<your-chat-id>"
```

## Recommended Models

| Model | Role | VRAM | Notes |
|---|---|---|---|
| `qwen3:8b` | Orchestrator | ~5-6GB | Research, planning, coordination |
| `qwen2.5-coder:7b` | Coding | ~5GB | Fast and solid for code |
| `qwen2.5-coder:14b` | Coding | ~10GB | Stronger |
| `deepseek-coder-v2:16b` | Coding | ~12GB | Strong, slower |
| `codellama:7b` | Light coding | ~5GB | Alternative option |

No GPU? CPU-only works, but is slower:

```bash
ollama pull qwen2.5-coder:3b  # lighter 3B model for CPU
```

## Architecture

```text
main.py
├── interfaces/
│   ├── cli.py           # Rich terminal UI
│   └── web/
│       ├── api.py       # FastAPI + WebSocket
│       └── static/      # HTML/CSS/JS frontend
├── agent/
│   ├── core.py          # ReAct orchestrator
│   ├── memory.py        # Short + long-term memory
│   └── tools/
│       ├── registry.py  # Tool registry
│       ├── shell.py     # bash/PowerShell
│       ├── file_ops.py  # File read/write/search
│       ├── code_runner.py # Python/Node.js
│       ├── computer_use.py # Observe/type/click/screenshot GUI automation
│       ├── web_search.py  # DuckDuckGo
│       └── git_ops.py   # Git commands
└── safety/
    └── confirm.py       # Human-in-the-loop gate
```

## License

MIT. Use freely.
