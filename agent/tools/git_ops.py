"""Git tools — status, diff, log."""
from __future__ import annotations
from agent.tools.shell import run_shell


async def git_status(path: str = ".") -> str:
    return await run_shell("git status", cwd=path)


async def git_diff(path: str = ".", staged: bool = False) -> str:
    cmd = "git diff --cached" if staged else "git diff"
    return await run_shell(cmd, cwd=path)


async def git_log(path: str = ".", n: int = 10) -> str:
    cmd = f"git log --oneline --graph --decorate -n {n}"
    return await run_shell(cmd, cwd=path)
