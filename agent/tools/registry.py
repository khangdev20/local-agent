"""
Tool registry — tất cả tools được đăng ký ở đây.
Thêm tool mới: tạo file trong agent/tools/, import và thêm vào TOOLS dict.
"""
from __future__ import annotations

from typing import Callable, Optional

from agent.tools.shell import run_shell
from agent.tools.file_ops import read_file, write_file, list_dir, search_files, patch_file
from agent.tools.code_runner import run_python, run_nodejs
from agent.tools.web_search import web_search
from agent.tools.git_ops import git_status, git_diff, git_log
from agent.tools.computer_use import (
    computer_click,
    computer_hotkey,
    computer_position,
    computer_press,
    computer_screenshot,
    computer_type,
)


# ── Tool registry ─────────────────────────────────────────────────────────────
# Format: tool_name → {fn, description, args schema}

TOOLS: dict[str, dict] = {
    # Shell
    "run_shell": {
        "fn": run_shell,
        "description": "Run a shell command (bash on Linux, PowerShell on Windows). Returns stdout+stderr.",
        "args": {"command": "string — the command to run", "cwd": "string (optional) — working directory"},
        "dangerous": True,
    },

    # File operations
    "read_file": {
        "fn": read_file,
        "description": "Read the contents of a file. Returns text content.",
        "args": {"path": "string — absolute or relative file path"},
        "dangerous": False,
    },
    "write_file": {
        "fn": write_file,
        "description": "Write (or overwrite) a file with given content.",
        "args": {"path": "string — file path", "content": "string — full file content"},
        "dangerous": True,
    },
    "patch_file": {
        "fn": patch_file,
        "description": "Replace a specific string in a file. Safer than full overwrite.",
        "args": {"path": "string", "old_str": "string — exact text to find", "new_str": "string — replacement"},
        "dangerous": False,
    },
    "list_dir": {
        "fn": list_dir,
        "description": "List files and directories at a path.",
        "args": {"path": "string — directory path", "recursive": "bool (optional, default false)"},
        "dangerous": False,
    },
    "search_files": {
        "fn": search_files,
        "description": "Search for text pattern in files (like grep). Returns matching lines with file paths.",
        "args": {"pattern": "string — text or regex", "path": "string — directory to search", "extension": "string (optional) — e.g. '.py'"},
        "dangerous": False,
    },

    # Code runners
    "run_python": {
        "fn": run_python,
        "description": "Execute a Python code snippet and return output.",
        "args": {"code": "string — Python code to execute", "timeout": "int (optional, default 30)"},
        "dangerous": True,
    },
    "run_nodejs": {
        "fn": run_nodejs,
        "description": "Execute a Node.js snippet and return output.",
        "args": {"code": "string — JavaScript code", "timeout": "int (optional, default 30)"},
        "dangerous": True,
    },

    # Computer use
    "computer_click": {
        "fn": computer_click,
        "description": "Click at screen coordinates in the active desktop session.",
        "args": {"x": "int — screen x coordinate", "y": "int — screen y coordinate", "clicks": "int (optional, default 1)", "button": "string (optional: left/right/middle)"},
        "dangerous": True,
    },
    "computer_type": {
        "fn": computer_type,
        "description": "Type text into the active application/window.",
        "args": {"text": "string — text to type", "interval": "float (optional, default 0.0 seconds between chars)"},
        "dangerous": True,
    },
    "computer_press": {
        "fn": computer_press,
        "description": "Press a single key in the active application/window.",
        "args": {"key": "string — key name, e.g. enter, tab, escape, left", "presses": "int (optional, default 1)"},
        "dangerous": True,
    },
    "computer_hotkey": {
        "fn": computer_hotkey,
        "description": "Press a key combination in the active application/window.",
        "args": {"keys": "array[string] — e.g. ['command', 'l'] or ['ctrl', 'c']"},
        "dangerous": True,
    },
    "computer_screenshot": {
        "fn": computer_screenshot,
        "description": "Take a screenshot of the current desktop and return the saved image path.",
        "args": {"path": "string (optional) — output PNG path"},
        "dangerous": False,
    },
    "computer_position": {
        "fn": computer_position,
        "description": "Return the current mouse position when supported by the local backend.",
        "args": {},
        "dangerous": False,
    },

    # Web
    "web_search": {
        "fn": web_search,
        "description": "Search DuckDuckGo for information. Returns top results with snippets.",
        "args": {"query": "string — search query", "max_results": "int (optional, default 5)"},
        "dangerous": False,
    },

    # Git
    "git_status": {
        "fn": git_status,
        "description": "Get git status of a repository.",
        "args": {"path": "string — repo directory"},
        "dangerous": False,
    },
    "git_diff": {
        "fn": git_diff,
        "description": "Show git diff for a repository.",
        "args": {"path": "string — repo directory", "staged": "bool (optional)"},
        "dangerous": False,
    },
    "git_log": {
        "fn": git_log,
        "description": "Show recent git commit log.",
        "args": {"path": "string — repo directory", "n": "int (optional, default 10)"},
        "dangerous": False,
    },
}


def get_tool(name: str) -> Optional[Callable]:
    entry = TOOLS.get(name)
    return entry["fn"] if entry else None


def is_dangerous(name: str) -> bool:
    entry = TOOLS.get(name)
    return bool(entry and entry.get("dangerous", False))
