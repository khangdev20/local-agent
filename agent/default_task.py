"""
Default idle task for the local agent.

This is used when the user intentionally asks the agent to do something useful
without providing a specific task.
"""
from __future__ import annotations

import os
from pathlib import Path


DEFAULT_IDLE_TASK = """You do not have a user-assigned task right now.

Use this as your default idle workflow:
1. Study one practical engineering topic that can improve future projects.
2. Rotate through these areas over time:
   - system design and architecture
   - web/app design and UX patterns
   - coding conventions for Next.js, React, Node.js, Fastify, .NET, React Native, NestJS, and related stacks
   - DevOps, CI/CD, observability, deployment, security, and reliability
3. Prefer official docs, framework guides, mature engineering blogs, and production-grade examples.
4. Compare a few sources when external research is needed, but keep queries generic and never include local/private data.
5. Produce a concise English learning note with:
   - topic studied
   - key principles
   - concrete conventions or checklist items
   - how to apply it to a real project
   - one suggested follow-up improvement or experiment

If a browser/ChatGPT web adapter exists in the available tools, you may use it.
Otherwise, use the available web_search tool.
"""


def get_default_task() -> str:
    """Return the configured idle task, falling back to the built-in workflow."""
    env_task = os.getenv("AGENT_DEFAULT_TASK")
    if env_task and env_task.strip():
        return env_task.strip()

    config_task = _read_default_task_from_config()
    if config_task:
        return config_task

    return DEFAULT_IDLE_TASK.strip()


def _read_default_task_from_config() -> str:
    """Read agent.default_task from config/default.yaml without a YAML dependency."""
    config_path = Path(__file__).resolve().parents[1] / "config" / "default.yaml"
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("default_task:"):
            value = stripped.removeprefix("default_task:").strip()
            if value.startswith("|"):
                value = "|"

            if value and value != "|":
                return value.strip('"').strip("'").strip()

            block: list[str] = []
            for block_line in lines[index + 1:]:
                if block_line.startswith("    "):
                    block.append(block_line[4:])
                elif not block_line.strip():
                    block.append("")
                else:
                    break
            return "\n".join(block).strip()

    return ""
