"""
Safety Gate — kiểm tra và yêu cầu xác nhận cho các lệnh nguy hiểm.
Human-in-the-loop: agent hỏi người dùng trước khi thực thi.
"""
from __future__ import annotations

import os
import re
from pathlib import Path


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

# Paths/files that may contain credentials or highly private local data.
# These are blocked even when auto_confirm=True.
BLOCKED_PATH_PATTERNS = [
    r"(^|/)\.ssh/(id_|.*_rsa|.*_dsa|.*_ecdsa|.*_ed25519)",
    r"(^|/)\.gnupg/",
    r"(^|/)Library/Keychains/",
    r"(^|/)AppData/Roaming/Microsoft/Credentials/",
]

# These are sometimes useful for development, but should not be touched without
# an explicit human approval.
SENSITIVE_PATH_PATTERNS = [
    r"(^|/)\.env(\..*)?$",
    r"(^|/)\.npmrc$",
    r"(^|/)\.pypirc$",
    r"(^|/)credentials(\.json|\.yml|\.yaml)?$",
    r"(^|/)secrets?(\.json|\.yml|\.yaml|\.toml|\.ini)?$",
    r"(^|/)config/gcloud/",
    r"(^|/)\.aws/",
    r"(^|/)\.azure/",
    r"(^|/)\.docker/config\.json$",
]

# Outbound network commands can leak local data. Confirmation is required if a
# shell/python/node snippet appears to make a network request.
OUTBOUND_NETWORK_PATTERNS = [
    r"\b(curl|wget|scp|rsync|nc|netcat|ftp|sftp)\b",
    r"\b(requests|httpx|urllib|fetch|axios)\b",
]

# Tools that always require confirmation
ALWAYS_CONFIRM_TOOLS = {
    "write_file",
    "run_shell",
    "run_python",
    "run_nodejs",
    "computer_click",
    "computer_type",
    "computer_press",
    "computer_hotkey",
}

LOCAL_ONLY_TOOLS = {"read_file", "write_file", "patch_file", "list_dir", "search_files"}
EXTERNAL_TOOLS = {"web_search"}
GUI_CONTROL_TOOLS = {"computer_click", "computer_type", "computer_press", "computer_hotkey"}


class SafetyGate:
    def __init__(self, auto_confirm: bool = False):
        """
        auto_confirm=True: skip all confirmations (headless/testing mode).
        auto_confirm=False: default interactive mode.
        """
        self.auto_confirm = auto_confirm
        self._blocked = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]
        self._confirm = [re.compile(p, re.IGNORECASE) for p in CONFIRM_PATTERNS]
        self._blocked_paths = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATH_PATTERNS]
        self._sensitive_paths = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_PATH_PATTERNS]
        self._outbound = [re.compile(p, re.IGNORECASE) for p in OUTBOUND_NETWORK_PATTERNS]

    def is_blocked(self, tool_name: str, args: dict) -> tuple[bool, str]:
        """Returns (is_blocked, reason)."""
        command = args.get("command", "") or args.get("code", "")
        for pattern in self._blocked:
            if pattern.search(command):
                return True, f"Blocked pattern detected: {pattern.pattern}"

        for path in self._paths_from_args(tool_name, args):
            display = self._display_path(path)
            for pattern in self._blocked_paths:
                if pattern.search(display):
                    return True, f"Privacy boundary: blocked access to secret path: {display}"

        if tool_name in EXTERNAL_TOOLS and self._contains_secret_like_text(args):
            return True, "Privacy boundary: blocked sending secret-like text to an external tool."

        return False, ""

    def requires_confirmation(self, tool_name: str, args: dict) -> bool:
        """Returns True if this action needs user confirmation."""
        if tool_name in EXTERNAL_TOOLS:
            # Outbound requests can reveal prompt/query text. Keep this boundary
            # visible even when users enable auto-confirm for local actions.
            return True

        if tool_name in LOCAL_ONLY_TOOLS and self._touches_sensitive_path(tool_name, args):
            return True

        if tool_name in GUI_CONTROL_TOOLS:
            return not self.auto_confirm

        if tool_name not in ALWAYS_CONFIRM_TOOLS:
            return False

        # write_file always needs confirm
        if tool_name == "write_file":
            return not self.auto_confirm

        # run_shell / run_python: check for suspicious patterns
        command = args.get("command", "") or args.get("code", "")
        if any(p.search(command) for p in self._outbound):
            return True
        if self.auto_confirm:
            return False
        return any(p.search(command) for p in self._confirm)

    def format_confirmation_prompt(self, tool_name: str, args: dict) -> str:
        """Format a human-readable confirmation prompt."""
        privacy_note = self._privacy_note(tool_name, args)
        if privacy_note:
            privacy_note = f"\n  Privacy: {privacy_note}"

        if tool_name == "run_shell":
            cmd = args.get("command", "")
            cwd = args.get("cwd", ".")
            return f"⚠️  Run shell command?\n  Command: {cmd}\n  Directory: {cwd}{privacy_note}"
        elif tool_name == "write_file":
            path = args.get("path", "")
            lines = args.get("content", "").count("\n") + 1
            return f"⚠️  Write file?\n  Path: {path}\n  Content: {lines} lines{privacy_note}"
        elif tool_name in ("run_python", "run_nodejs"):
            code_preview = args.get("code", "")[:200]
            lang = "Python" if tool_name == "run_python" else "Node.js"
            return f"⚠️  Execute {lang} code?\n  Code preview: {code_preview}...{privacy_note}"
        elif tool_name == "computer_click":
            return f"⚠️  Click screen?\n  Coordinates: ({args.get('x')}, {args.get('y')})\n  Button: {args.get('button', 'left')}\n  Clicks: {args.get('clicks', 1)}{privacy_note}"
        elif tool_name == "computer_type":
            text = args.get("text", "")
            preview = text[:120] + ("..." if len(text) > 120 else "")
            return f"⚠️  Type into active app?\n  Text preview: {preview}{privacy_note}"
        elif tool_name == "computer_press":
            return f"⚠️  Press key in active app?\n  Key: {args.get('key')}\n  Presses: {args.get('presses', 1)}{privacy_note}"
        elif tool_name == "computer_hotkey":
            return f"⚠️  Press hotkey in active app?\n  Keys: {args.get('keys')}{privacy_note}"
        return f"⚠️  Execute {tool_name} with args: {args}{privacy_note}"

    def _touches_sensitive_path(self, tool_name: str, args: dict) -> bool:
        return any(
            pattern.search(self._display_path(path))
            for path in self._paths_from_args(tool_name, args)
            for pattern in self._sensitive_paths
        )

    def _privacy_note(self, tool_name: str, args: dict) -> str:
        if tool_name in EXTERNAL_TOOLS:
            return "This sends query text outside this machine."

        command = args.get("command", "") or args.get("code", "")
        if any(p.search(command) for p in self._outbound):
            return "This may make an outbound network request."

        if self._touches_sensitive_path(tool_name, args):
            return "This touches a file/path that may contain secrets or private data."

        return ""

    @staticmethod
    def _paths_from_args(tool_name: str, args: dict) -> list[Path]:
        keys = ("path", "cwd")
        paths = []
        for key in keys:
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                paths.append(Path(value).expanduser())
        return paths

    @staticmethod
    def _display_path(path: Path) -> str:
        try:
            return str(path.resolve())
        except OSError:
            return os.path.normpath(str(path))

    @staticmethod
    def _contains_secret_like_text(args: dict) -> bool:
        text = " ".join(str(v) for v in args.values())
        return bool(re.search(
            r"(api[_-]?key|secret|token|password|private[_-]?key|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
            text,
            re.IGNORECASE,
        ))
