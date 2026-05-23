"""
Tool registry: all tools are registered here.
To add a new tool, create a file in agent/tools/, import it, and add it to TOOLS.
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
    computer_focus_app,
    computer_hotkey,
    computer_observe,
    computer_position,
    computer_press,
    computer_screenshot,
    computer_type,
)
from agent.tools.browser import (
    browser_open,
    browser_type,
    browser_click,
    browser_press_key,
    browser_get_content,
    browser_screenshot,
    browser_close,
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
    "computer_observe": {
        "fn": computer_observe,
        "description": "Observe the active app/window using accessibility data. Returns visible UI roles, names, values, positions, and sizes when available.",
        "args": {"max_depth": "int (optional, default 3)", "max_items": "int (optional, default 120)"},
        "dangerous": False,
    },
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
    "computer_focus_app": {
        "fn": computer_focus_app,
        "description": "Focus/activate a specific desktop application by name (macOS only) e.g., 'Cursor' or 'Google Chrome'.",
        "args": {"app_name": "string — name of application"},
        "dangerous": True,
    },

    # Web
    "web_search": {
        "fn": web_search,
        "description": "Search DuckDuckGo for information. Returns top results with snippets.",
        "args": {"query": "string — search query", "max_results": "int (optional, default 5)"},
        "dangerous": False,
    },
    "browser_open": {
        "fn": browser_open,
        "description": "Open a headful browser with persistent context and navigate to a URL. Persists cookies and session state.",
        "args": {"url": "string (optional) — URL to navigate to"},
        "dangerous": False,
    },
    "browser_type": {
        "fn": browser_type,
        "description": "Type text into an input field on the active browser page using a CSS selector.",
        "args": {"selector": "string — CSS selector", "text": "string — text to type"},
        "dangerous": False,
    },
    "browser_click": {
        "fn": browser_click,
        "description": "Click an element on the active browser page using a CSS selector.",
        "args": {"selector": "string — CSS selector"},
        "dangerous": False,
    },
    "browser_press_key": {
        "fn": browser_press_key,
        "description": "Press a keyboard key in the browser page (e.g. 'Enter', 'Tab').",
        "args": {"key": "string — key name"},
        "dangerous": False,
    },
    "browser_get_content": {
        "fn": browser_get_content,
        "description": "Retrieve the visible text content of the active browser page.",
        "args": {},
        "dangerous": False,
    },
    "browser_screenshot": {
        "fn": browser_screenshot,
        "description": "Capture a screenshot of the active browser page and return the saved path.",
        "args": {"path": "string (optional) — path to save PNG"},
        "dangerous": False,
    },
    "browser_close": {
        "fn": browser_close,
        "description": "Close the active browser instance.",
        "args": {},
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
