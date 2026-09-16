"""
SQLite-backed session store (architecture doc, Section 2.1 / component
table). File-based, mounted as a volume rather than run as its own
container — see README "Design decisions made while scaffolding".
"""

import sqlite3
from contextlib import contextmanager

from app.core.config import settings


@contextmanager
def _connection():
    conn = sqlite3.connect(settings.session_db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the conversation-history table if it doesn't exist yet.

    TODO (Sprint 3): call this on backend startup; define the schema
    (session_id, role, content, timestamp) needed for multi-turn history.
    """
    raise NotImplementedError


def get_history(session_id: str) -> list[dict]:
    """TODO (Sprint 3): return the conversation history for a session."""
    raise NotImplementedError


def append_exchange(session_id: str, question: str, answer: str) -> None:
    """TODO (Sprint 3): persist a question/answer pair for a session."""
    raise NotImplementedError
