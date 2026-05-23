"""
Optional notification integrations for local-agent.
"""
from __future__ import annotations

import os
import textwrap
from html import escape

import httpx


TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_TELEGRAM_TEXT = 3900


def telegram_is_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


async def send_telegram_message(text: str) -> tuple[bool, str]:
    """Send a Telegram message when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are configured."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return False, "Telegram notifications are not configured."

    message = text.strip()
    if len(message) > MAX_TELEGRAM_TEXT:
        message = message[:MAX_TELEGRAM_TEXT] + "\n..."

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as e:
        return False, f"Telegram notification failed: {e}"

    return True, "Telegram notification sent."


def format_task_status_message(task_id: str, state: dict, headline: str | None = None) -> str:
    """Build a compact Telegram-safe task status message."""
    title = headline or "Local Agent task status"
    status = state.get("status", "unknown")
    model = state.get("model", "unknown")
    task = _truncate(str(state.get("task", "")), 240)
    answer = _truncate(str(state.get("answer") or ""), 500)
    error = _truncate(str(state.get("error") or ""), 500)
    pending = state.get("pending_confirmation")

    lines = [
        f"<b>{escape(title)}</b>",
        f"Status: <code>{escape(status)}</code>",
        f"Task ID: <code>{escape(task_id)}</code>",
        f"Model: <code>{escape(model)}</code>",
    ]

    if task:
        lines.extend(["", "<b>Task</b>", escape(task)])

    if pending:
        tool = escape(str(pending.get("tool", "unknown")))
        lines.extend(["", "<b>Waiting for confirmation</b>", f"Tool: <code>{tool}</code>"])

    if answer and status == "completed":
        lines.extend(["", "<b>Answer preview</b>", escape(answer)])

    if error:
        lines.extend(["", "<b>Error</b>", escape(error)])

    return "\n".join(lines)


def _truncate(text: str, limit: int) -> str:
    cleaned = textwrap.shorten(" ".join(text.split()), width=limit, placeholder="...")
    return cleaned.strip()
