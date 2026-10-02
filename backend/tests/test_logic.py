"""Self-checks for backend logic that needs no models, Qdrant or Ollama.

Run from backend/:  python -m tests.test_logic
"""

import tempfile
from pathlib import Path

from app.core.config import settings
from app.db import session_store
from app.services.retrieval import _reciprocal_rank_fusion


def test_rrf_dedupes_on_luat_dieu_khoan() -> None:
    a = {"payload": {"luat": "L", "dieu": "Điều 1", "khoan": None}}
    b = {"payload": {"luat": "L", "dieu": "Điều 2", "khoan": "Khoản 1"}}
    c = {"payload": {"luat": "L", "dieu": "Điều 2", "khoan": "Khoản 2"}}
    merged = _reciprocal_rank_fusion([[a, b], [b, c]])
    keys = [(m["payload"]["dieu"], m["payload"]["khoan"]) for m in merged]
    # b is in both lists -> deduped and ranked first; same Điều, different Khoản stay separate.
    assert keys == [("Điều 2", "Khoản 1"), ("Điều 1", None), ("Điều 2", "Khoản 2")], keys


def test_session_store_round_trips_citations() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        settings.session_db_path = str(Path(tmp) / "session.db")
        session_store.init_db()
        citation = {"luat": "Bộ luật Lao động 2019", "dieu": "Điều 36", "khoan": None}
        session_store.append_exchange("s1", "q1", "a1", {"citations": [citation]})
        session_store.append_exchange("s1", "q2", "fallback", {"is_fallback": True})

        history = session_store.get_history("s1")
        assert history == [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1", "citations": [citation]},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "fallback", "is_fallback": True},
        ], history
        # limit keeps the most recent messages, still oldest first
        assert [m["content"] for m in session_store.get_history("s1", limit=2)] == ["q2", "fallback"]


if __name__ == "__main__":
    test_rrf_dedupes_on_luat_dieu_khoan()
    test_session_store_round_trips_citations()
    print("backend logic OK")
