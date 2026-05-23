"""
File operations — đọc, ghi, tìm kiếm file cho coding agent.
"""
from __future__ import annotations

import asyncio
import fnmatch
import os
import re
from pathlib import Path
from typing import Optional


MAX_READ_CHARS = 12_000
MAX_SEARCH_RESULTS = 50


async def read_file(path: str) -> str:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"Error: File not found: {path}"
    if not p.is_file():
        return f"Error: Path is not a file: {path}"

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        return f"Error: Permission denied reading {path}"

    lines = text.splitlines()
    # Add line numbers (useful for code)
    numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))

    if len(numbered) > MAX_READ_CHARS:
        numbered = numbered[:MAX_READ_CHARS] + f"\n... [truncated — {len(lines)} lines total]"

    return f"File: {p}\n{'─'*60}\n{numbered}"


async def write_file(path: str, content: str) -> str:
    p = Path(path).expanduser().resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        lines = content.count("\n") + 1
        return f"✓ Written {lines} lines to {p}"
    except PermissionError:
        return f"Error: Permission denied writing to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


async def patch_file(path: str, old_str: str, new_str: str) -> str:
    """Replace a unique string in a file. Safer than full overwrite."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"Error: File not found: {path}"

    text = p.read_text(encoding="utf-8", errors="replace")
    count = text.count(old_str)

    if count == 0:
        return f"Error: String not found in {path}. Cannot patch."
    if count > 1:
        return f"Error: String found {count} times — must be unique to patch safely."

    new_text = text.replace(old_str, new_str, 1)
    p.write_text(new_text, encoding="utf-8")
    return f"✓ Patched {p} — replaced 1 occurrence."


async def list_dir(path: str = ".", recursive: bool = False) -> str:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return f"Error: Path not found: {path}"
    if not p.is_dir():
        return f"Error: Not a directory: {path}"

    lines = [f"Directory: {p}\n"]

    IGNORE = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", "dist", "build"}

    if recursive:
        for item in sorted(p.rglob("*")):
            # Skip ignored directories
            if any(part in IGNORE for part in item.parts):
                continue
            rel = item.relative_to(p)
            prefix = "  " * (len(rel.parts) - 1)
            icon = "📁" if item.is_dir() else "📄"
            lines.append(f"{prefix}{icon} {item.name}")
    else:
        for item in sorted(p.iterdir()):
            if item.name in IGNORE:
                continue
            icon = "📁" if item.is_dir() else "📄"
            size = "" if item.is_dir() else f"  ({item.stat().st_size:,} bytes)"
            lines.append(f"{icon} {item.name}{size}")

    result = "\n".join(lines)
    if len(result) > MAX_READ_CHARS:
        result = result[:MAX_READ_CHARS] + "\n... [truncated]"
    return result


async def search_files(pattern: str, path: str = ".", extension: Optional[str] = None) -> str:
    """Search for text pattern in files recursively (like grep)."""
    base = Path(path).expanduser().resolve()
    if not base.exists():
        return f"Error: Path not found: {path}"

    IGNORE = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
    results = []

    for file_path in sorted(base.rglob("*")):
        # Skip ignored dirs
        if any(part in IGNORE for part in file_path.parts):
            continue
        if not file_path.is_file():
            continue
        if extension and not file_path.suffix == extension:
            continue

        # Skip binary files
        try:
            text = file_path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, PermissionError):
            continue

        for lineno, line in enumerate(text.splitlines(), 1):
            if re.search(pattern, line, re.IGNORECASE):
                rel = file_path.relative_to(base)
                results.append(f"{rel}:{lineno}: {line.strip()}")
                if len(results) >= MAX_SEARCH_RESULTS:
                    results.append(f"... [stopped at {MAX_SEARCH_RESULTS} results]")
                    return "\n".join(results)

    if not results:
        return f"No matches for '{pattern}' in {path}"
    return f"Found {len(results)} match(es):\n" + "\n".join(results)
