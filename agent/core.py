"""
Agent core: ReAct (Reason + Act) loop with an Ollama backend.
Supports streaming, tool calling, and memory management.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

import httpx

from agent.memory import Memory
from agent.tools.registry import TOOLS, get_tool
from safety.confirm import SafetyGate


# ── Model constants ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a local AI coding assistant that can control the computer to help with software development.

You have access to these tools:
{tool_descriptions}

RULES:
- Think step-by-step before acting
- Use tools to get real information — never guess file contents or command output
- Always use EXACT format below for tool calls
- After getting a tool result, reason about it before the next step
- When done, provide a clear summary
- For product ideas: first clarify the user goal, research the path to market, identify target users, distribution channels, risks, and an implementation plan before changing code
- For implementation: work feature-by-feature, inspect git status first, use a clear feature branch when the repo is under git, keep changes scoped, run relevant checks, then summarize a PR-ready diff
- For merges: never merge or delete branches without explicit user approval; prefer PR-style review and safe merge steps
- Use external research tools only with confirmation, and never include private local data in research queries
- Privacy boundary: do not read secrets, credentials, browser profiles, keychains, SSH/GPG keys, or private user files unless the user explicitly asks for that exact data
- Privacy boundary: never send local file contents, credentials, environment variables, tokens, or proprietary code to external tools such as web_search
- Prefer local tools over network tools; ask the user before any outbound request
- For GUI/browser work: use computer_observe before computer_click/computer_type/computer_press whenever possible, then choose coordinates from the observed UI element positions/sizes.
- If computer_observe cannot read the screen, ask the user to grant Accessibility permission or provide the needed location before clicking blindly.

TOOL CALL FORMAT (use exactly):
<tool_call>
{{"tool": "tool_name", "args": {{"arg1": "value1"}}}}
</tool_call>

TOOL RESULT will appear as:
<tool_result>
...result...
</tool_result>

Think, then act, then observe, then repeat until task is complete.
"""

FAST_SYSTEM_PROMPT = """You are a fast local assistant.

Reply directly and concisely. Do not use tools. Do not expose hidden reasoning.
If the user asks for work that requires files, commands, browser actions, or external facts,
say what you can answer immediately and suggest switching to Agent mode for tool use.
"""


@dataclass
class Step:
    thought: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    is_final: bool = False


@dataclass
class AgentResult:
    success: bool
    answer: str
    steps: list[Step] = field(default_factory=list)
    error: str = ""
    elapsed: float = 0.0


class Agent:
    def __init__(
        self,
        model: str = "qwen3:8b",
        ollama_url: str = "http://localhost:11434",
        max_steps: int = 15,
        temperature: float = 0.2,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.max_steps = max_steps
        self.temperature = temperature
        self.memory = Memory()
        self.safety = SafetyGate()
        self._client = httpx.AsyncClient(timeout=120.0)

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(self, task: str, confirm_fn=None) -> AgentResult:
        """Run agent synchronously (collects all steps)."""
        steps: list[Step] = []
        answer = ""
        start = time.time()

        try:
            async for chunk in self._react_loop(task, confirm_fn):
                if isinstance(chunk, Step):
                    steps.append(chunk)
                elif isinstance(chunk, str):
                    answer = chunk
        except Exception as e:
            return AgentResult(success=False, answer="", steps=steps, error=str(e), elapsed=time.time() - start)

        self.memory.add_turn(task, answer)
        return AgentResult(success=True, answer=answer, steps=steps, elapsed=time.time() - start)

    async def stream(self, task: str, confirm_fn=None) -> AsyncGenerator[dict, None]:
        """Stream agent progress as events for WebSocket / SSE."""
        steps: list[Step] = []
        start = time.time()

        try:
            async for chunk in self._react_loop(task, confirm_fn):
                if isinstance(chunk, Step):
                    steps.append(chunk)
                    yield {"type": "step", "data": self._step_to_dict(chunk)}
                elif isinstance(chunk, str):
                    self.memory.add_turn(task, chunk)
                    yield {"type": "final", "data": {"answer": chunk, "elapsed": round(time.time() - start, 2)}}
        except Exception as e:
            yield {"type": "error", "data": {"message": str(e)}}

    async def fast_reply(self, task: str, model: str | None = None) -> str:
        """Return a direct no-tool response for low-latency UI interactions."""
        messages = [
            {"role": "system", "content": FAST_SYSTEM_PROMPT},
        ]

        history = self.memory.get_recent(n=2)
        for turn in history:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["assistant"]})

        messages.append({"role": "user", "content": task})
        answer = await self._call_ollama(messages, model=model, num_ctx=2048)
        self.memory.add_turn(task, answer)
        return answer

    # ── ReAct loop ────────────────────────────────────────────────────────────

    async def _react_loop(self, task: str, confirm_fn=None) -> AsyncGenerator:
        messages = self._build_messages(task)

        for step_num in range(self.max_steps):
            # 1. LLM generates next thought/action
            response_text = await self._call_ollama(messages)

            # 2. Parse tool call (if any)
            tool_call = self._parse_tool_call(response_text)

            if tool_call is None:
                # No tool call → this is the final answer
                step = Step(thought=response_text, is_final=True)
                yield step
                yield response_text
                return

            tool_name, tool_args = tool_call
            thought = self._extract_thought(response_text)

            # 3. Safety/privacy check before any tool execution
            is_blocked, blocked_reason = self.safety.is_blocked(tool_name, tool_args)
            if is_blocked:
                tool_result = f"Blocked by safety/privacy gate: {blocked_reason}"
            elif self.safety.requires_confirmation(tool_name, tool_args):
                if confirm_fn:
                    approved = await confirm_fn(tool_name, tool_args)
                else:
                    approved = False
                if not approved:
                    tool_result = "Action requires human confirmation and was not executed."
                else:
                    tool_result = await self._execute_tool(tool_name, tool_args)
            else:
                tool_result = await self._execute_tool(tool_name, tool_args)

            step = Step(
                thought=thought,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
            )
            yield step

            # 4. Append to conversation
            messages.append({"role": "assistant", "content": response_text})
            
            images = []
            if "screenshot saved to" in tool_result.lower():
                import os
                import base64
                match = re.search(r"saved to\s+(.*)", tool_result, re.IGNORECASE)
                if match:
                    img_path = match.group(1).strip()
                    try:
                        if os.path.exists(img_path):
                            with open(img_path, "rb") as f:
                                encoded_image = base64.b64encode(f.read()).decode("utf-8")
                                images.append(encoded_image)
                    except Exception:
                        pass

            user_message: dict[str, Any] = {
                "role": "user",
                "content": f"<tool_result>\n{tool_result}\n</tool_result>\n\nContinue."
            }
            if images:
                user_message["images"] = images
                
            messages.append(user_message)

        # Max steps reached
        yield Step(thought="Max steps reached.", is_final=True)
        yield "Task reached maximum steps. Here is what was accomplished so far."

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_messages(self, task: str) -> list[dict]:
        tool_descriptions = "\n".join(
            f"- {name}: {info['description']}\n  args: {json.dumps(info['args'])}"
            for name, info in TOOLS.items()
        )
        system = SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)
        messages = [{"role": "system", "content": system}]

        # Add memory context
        history = self.memory.get_recent(n=4)
        for turn in history:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["assistant"]})

        messages.append({"role": "user", "content": task})
        return messages

    async def _call_ollama(self, messages: list[dict], model: str | None = None, num_ctx: int = 8192) -> str:
        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": num_ctx},
        }
        resp = await self._client.post(f"{self.ollama_url}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    async def _execute_tool(self, name: str, args: dict) -> str:
        tool_fn = get_tool(name)
        if tool_fn is None:
            return f"Error: Unknown tool '{name}'"
        try:
            result = await tool_fn(**args)
            return str(result)
        except Exception as e:
            return f"Tool error: {e}"

    @staticmethod
    def _parse_tool_call(text: str) -> Optional[tuple[str, dict]]:
        match = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
            return data["tool"], data.get("args", {})
        except (json.JSONDecodeError, KeyError):
            return None

    @staticmethod
    def _extract_thought(text: str) -> str:
        clean = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.DOTALL).strip()
        return clean[:500] if len(clean) > 500 else clean

    @staticmethod
    def _step_to_dict(step: Step) -> dict:
        return {
            "thought": step.thought,
            "tool_name": step.tool_name,
            "tool_args": step.tool_args,
            "tool_result": step.tool_result,
            "is_final": step.is_final,
        }

    async def close(self):
        await self._client.aclose()
