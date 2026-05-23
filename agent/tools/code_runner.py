"""
Code runner: execute Python and Node.js snippets safely.
Uses subprocesses with timeouts instead of direct exec().
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import os
from pathlib import Path


DEFAULT_TIMEOUT = 30
MAX_OUTPUT = 5000


async def _run_in_subprocess(cmd: list[str], code: str, timeout: int) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=cmd[-1] if cmd[-1].endswith((".py", ".js")) else ".tmp",
        delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd[:-1], tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return f"Error: Code timed out after {timeout}s."

        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")

        parts = []
        if out.strip():
            parts.append(out.strip())
        if err.strip():
            parts.append(f"[stderr]\n{err.strip()}")
        if proc.returncode != 0:
            parts.insert(0, f"[exit code {proc.returncode}]")

        result = "\n".join(parts) or "(no output)"
        if len(result) > MAX_OUTPUT:
            result = result[:MAX_OUTPUT] + f"\n... [truncated]"
        return result

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Execute Python code and return output."""
    python_exe = sys.executable  # same Python as the agent
    return await _run_in_subprocess([python_exe, "__placeholder__.py"], code, timeout)


async def run_nodejs(code: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Execute Node.js code and return output."""
    return await _run_in_subprocess(["node", "__placeholder__.js"], code, timeout)
