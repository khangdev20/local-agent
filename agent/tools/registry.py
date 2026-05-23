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
