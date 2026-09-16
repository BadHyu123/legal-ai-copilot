"""
Read-only endpoint so the frontend can reload a past conversation's
messages when the person switches to it in the sidebar (Sprint 3). The
frontend keeps its own local list of which session_ids exist and their
display titles (a UI convenience); this endpoint is the source of truth
for message content, since that's what's actually in the Session store.
"""

from fastapi import APIRouter

from app.db import session_store

router = APIRouter(tags=["sessions"])


@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str) -> list[dict]:
    return session_store.get_history(session_id, limit=200)
