"""
SQLite-backed session store (architecture doc, Section 2.1 / component
table). File-based, mounted as a volume rather than run as its own
container — see README "Design decisions made while scaffolding".
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings


@contextmanager
def _connection():
    Path(settings.session_db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.session_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the conversation-history table if it doesn't exist yet.
    Called once on backend startup (see app/main.py).
    """
    with _connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)"
        )


def get_history(session_id: str, limit: int = 20) -> list[dict]:
    """Return the most recent `limit` messages for a session, oldest first."""
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content FROM (
                SELECT id, role, content FROM messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
            ) ORDER BY id ASC
            """,
            (session_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def append_exchange(session_id: str, question: str, answer: str) -> None:
    """Persist a question/answer pair for a session, as two messages."""
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
            (session_id, question, now),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
            (session_id, answer, now),
        )
