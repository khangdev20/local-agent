"""
Shell tool: run bash commands on Linux/macOS or PowerShell on Windows.
Cross-platform, with timeout and stdout/stderr capture.
"""
from __future__ import annotations

import asyncio
import os
import platform
import sys
from pathlib import Path


IS_WINDOWS = platform.system() == "Windows"
DEFAULT_TIMEOUT = 60  # seconds
MAX_OUTPUT_CHARS = 8000  # truncate long output


async def run_shell(command: str, cwd: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    Run a shell command asynchronously.
    - Linux/Mac: bash -c "command"
    - Windows: powershell -Command "command"
    Returns combined stdout + stderr (truncated if too long).
    """
    working_dir = None
    if cwd:
        working_dir = Path(cwd).expanduser().resolve()
        if not working_dir.exists():
            return f"Error: Directory '{cwd}' does not exist."

    if IS_WINDOWS:
        proc_args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
    else:
        proc_args = ["bash", "-c", command]

    try:
        proc = await asyncio.create_subprocess_exec(
            *proc_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(working_dir) if working_dir else None,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return f"Error: Command timed out after {timeout}s."

        output_parts = []
        if stdout:
            output_parts.append(stdout.decode("utf-8", errors="replace"))
        if stderr:
            stderr_text = stderr.decode("utf-8", errors="replace")
            if stderr_text.strip():
                output_parts.append(f"[stderr]\n{stderr_text}")

        result = "\n".join(output_parts).strip()

        if proc.returncode != 0:
            result = f"[exit code {proc.returncode}]\n{result}"

        if len(result) > MAX_OUTPUT_CHARS:
            result = result[:MAX_OUTPUT_CHARS] + f"\n... [truncated, {len(result)} chars total]"

        return result or "(no output)"

    except FileNotFoundError:
        shell = "powershell" if IS_WINDOWS else "bash"
        return f"Error: Shell '{shell}' not found on this system."
    except Exception as e:
        return f"Error executing command: {e}"
