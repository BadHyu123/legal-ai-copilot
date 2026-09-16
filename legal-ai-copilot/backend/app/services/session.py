"""Thin service layer over app.db.session_store for the /ask endpoint. Sprint 3 backlog item."""

from app.db import session_store


def load_history(session_id: str) -> list[dict]:
    return session_store.get_history(session_id)


def save_exchange(session_id: str, question: str, answer: str) -> None:
    session_store.append_exchange(session_id, question, answer)
