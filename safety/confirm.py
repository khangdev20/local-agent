"""
Safety Gate — kiểm tra và yêu cầu xác nhận cho các lệnh nguy hiểm.
Human-in-the-loop: agent hỏi người dùng trước khi thực thi.
"""
from __future__ import annotations

import re
from typing import Optional


# Patterns that are always blocked (never executed)
BLOCKED_PATTERNS = [
    r"\brm\s+-rf\s+/\b",          # rm -rf /
    r"\bformat\b.*\b[cC]:\b",     # Windows format C:
    r"\bdd\s+if=.*of=/dev/[sh]d", # dd to disk
    r":\(\)\{.*fork.*bomb",       # fork bomb
    r"\bsudo\s+rm\s+-rf\b",       # sudo rm -rf
    r"shutdown\s+(-h\s+now|-r\s+now)",  # immediate shutdown
]

# Patterns that require user confirmation
CONFIRM_PATTERNS = [
    r"\brm\b",               # any rm command
    r"\bdel\b",              # Windows delete
    r"\bkill\b",             # kill processes
    r"\bpkill\b",
    r"\bchmod\b",            # permission changes
    r"\bchown\b",
    r"\bsudo\b",             # sudo anything
    r"\bpip\s+install\b",   # package installs
    r"\bnpm\s+install\b",
    r"\bapt\b",              # system package manager
    r"\byum\b",
    r"\bsystemctl\b",        # service management
    r"\bnet\s+(start|stop)\b",  # Windows services
    r"\bcurl.*\|\s*bash",   # curl pipe to bash
    r"\bwget.*\|\s*bash",
]

# Tools that always require confirmation
ALWAYS_CONFIRM_TOOLS = {"write_file", "run_shell", "run_python", "run_nodejs"}


class SafetyGate:
    def __init__(self, auto_confirm: bool = False):
        """
        auto_confirm=True: skip all confirmations (headless/testing mode).
        auto_confirm=False: default interactive mode.
        """
        self.auto_confirm = auto_confirm
        self._blocked = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]
        self._confirm = [re.compile(p, re.IGNORECASE) for p in CONFIRM_PATTERNS]

    def is_blocked(self, tool_name: str, args: dict) -> tuple[bool, str]:
        """Returns (is_blocked, reason)."""
        command = args.get("command", "") or args.get("code", "")
        for pattern in self._blocked:
            if pattern.search(command):
                return True, f"Blocked pattern detected: {pattern.pattern}"
        return False, ""

    def requires_confirmation(self, tool_name: str, args: dict) -> bool:
        """Returns True if this action needs user confirmation."""
        if self.auto_confirm:
            return False

        if tool_name not in ALWAYS_CONFIRM_TOOLS:
            return False

        # write_file always needs confirm
        if tool_name == "write_file":
            return True

        # run_shell / run_python: check for suspicious patterns
        command = args.get("command", "") or args.get("code", "")
        return any(p.search(command) for p in self._confirm)

    def format_confirmation_prompt(self, tool_name: str, args: dict) -> str:
        """Format a human-readable confirmation prompt."""
        if tool_name == "run_shell":
            cmd = args.get("command", "")
            cwd = args.get("cwd", ".")
            return f"⚠️  Run shell command?\n  Command: {cmd}\n  Directory: {cwd}"
        elif tool_name == "write_file":
            path = args.get("path", "")
            lines = args.get("content", "").count("\n") + 1
            return f"⚠️  Write file?\n  Path: {path}\n  Content: {lines} lines"
        elif tool_name in ("run_python", "run_nodejs"):
            code_preview = args.get("code", "")[:200]
            lang = "Python" if tool_name == "run_python" else "Node.js"
            return f"⚠️  Execute {lang} code?\n  Code preview: {code_preview}..."
        return f"⚠️  Execute {tool_name} with args: {args}"
