"""
Memory management: short-term conversation buffer + long-term SQLite store.
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections import deque
from pathlib import Path
from typing import Optional


class Memory:
    """
    Short-term: in-memory deque (last N turns, fits context window).
    Long-term: SQLite for task history and notes.
    """

    def __init__(self, db_path: str = "~/.local-agent/memory.db", max_short: int = 20):
        self._short: deque[dict] = deque(maxlen=max_short)
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Short-term ────────────────────────────────────────────────────────────

    def add_turn(self, user: str, assistant: str) -> None:
        turn = {"user": user, "assistant": assistant, "ts": time.time()}
        self._short.append(turn)
        self._save_to_db(turn)

    def get_recent(self, n: int = 4) -> list[dict]:
        items = list(self._short)
        return items[-n:] if len(items) >= n else items

    def clear_short(self) -> None:
        self._short.clear()

    # ── Long-term (SQLite) ────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Basic keyword search in long-term history."""
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT user, assistant, ts FROM turns "
                "WHERE user LIKE ? OR assistant LIKE ? "
                "ORDER BY ts DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        return [{"user": r[0], "assistant": r[1], "ts": r[2]} for r in rows]

    def save_note(self, key: str, value: str) -> None:
        """Save a named note (e.g. project context, user preferences)."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO notes(key, value, ts) VALUES(?,?,?)",
                (key, value, time.time()),
            )

    def get_note(self, key: str) -> Optional[str]:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT value FROM notes WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def get_stats(self) -> dict:
        with sqlite3.connect(self._db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
            notes = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        return {"total_turns": total, "notes": notes, "short_term_loaded": len(self._short)}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT, assistant TEXT, ts REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    key TEXT PRIMARY KEY, value TEXT, ts REAL
                )
            """)

    def _save_to_db(self, turn: dict) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO turns(user, assistant, ts) VALUES(?,?,?)",
                (turn["user"], turn["assistant"], turn["ts"]),
            )
