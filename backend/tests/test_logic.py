"""Self-checks for backend logic that needs no models, Qdrant or Ollama.

Run from backend/:  python -m tests.test_logic
"""

import tempfile
from pathlib import Path

from app.api.routes.ask import is_refusal
from app.core.config import settings
from app.db import session_store
from app.services.retrieval import _reciprocal_rank_fusion


def test_is_refusal_only_on_leading_not_found() -> None:
    assert is_refusal("Không tìm thấy quy định pháp luật phù hợp với câu hỏi này.")
    assert is_refusal("**Không có quy định** cụ thể về vấn đề này trong căn cứ.")
    # Seen live: a lead-in before the refusal.
    assert is_refusal("Để trả lời câu hỏi này, tôi không tìm thấy quy định pháp luật nào liên quan "
                      "đến thủ tục làm hộ chiếu trong các căn cứ được cung cấp.")
    # An answer that cites the law is an answer, even if it notes a gap.
    assert not is_refusal("Không có quy định riêng về thưởng Tết, nhưng theo Điều 3 đây là thu nhập chịu thuế.")
    assert not is_refusal("Theo Điều 10, mức giảm trừ là 15,5 triệu đồng. Không tìm thấy quy định về mức khác.")
    assert not is_refusal("Mức giảm trừ gia cảnh là 15,5 triệu đồng/tháng.")


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
    test_is_refusal_only_on_leading_not_found()
    test_rrf_dedupes_on_luat_dieu_khoan()
    test_session_store_round_trips_citations()
    print("backend logic OK")
