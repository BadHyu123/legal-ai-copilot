"""Self-checks for backend logic that needs no models, Qdrant or Ollama.

Run from backend/:  python -m tests.test_logic
"""

import io
import tempfile
import zipfile
from pathlib import Path

from app.api.routes.ask import is_refusal
from app.core.config import settings
from app.db import session_store
from app.services import review
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


def test_split_clauses() -> None:
    contract = ("HỢP ĐỒNG LAO ĐỘNG\nBên A: Công ty X, địa chỉ ...\n"
                "Điều 1: Thời hạn và công việc\nHợp đồng xác định thời hạn 12 tháng.\n"
                "Điều 2: Chế độ làm việc\n1. Thời giờ làm việc 8 giờ/ngày.\n2. Thử việc 90 ngày.\n")
    assert review.split_clauses(contract) == [
        "Điều 1: Thời hạn và công việc\nHợp đồng xác định thời hạn 12 tháng.",
        "Điều 2: Chế độ làm việc\n1. Thời giờ làm việc 8 giờ/ngày.\n2. Thử việc 90 ngày."]
    # No "Điều" headings: numbered items are the clauses; the preamble is dropped.
    assert review.split_clauses("Ký tên\n1. Lương 10 triệu đồng mỗi tháng, trả ngày 10.\n"
                                "2. Người lao động phải nộp tiền đặt cọc 5 triệu.") == [
        "1. Lương 10 triệu đồng mỗi tháng, trả ngày 10.", "2. Người lao động phải nộp tiền đặt cọc 5 triệu."]
    # A long clause is cut at line boundaries; each part keeps its heading.
    long_lines = "\n".join(f"{i}. " + "nghĩa vụ " * 30 for i in range(1, 9))
    parts = review.split_clauses(f"Điều 3. Nghĩa vụ\n{long_lines}\nĐiều 4. Khác\nNội dung đủ dài để giữ lại.")
    assert len(parts) > 2 and all(p.startswith("Điều 3. Nghĩa vụ\n") for p in parts[:-1])
    assert all(len(p) <= review.MAX_CLAUSE_CHARS for p in parts)


def test_extract_text_docx_and_errors() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", '<w:document><w:body><w:p><w:r><w:t>Điều 1. </w:t></w:r>'
                   '<w:r><w:t xml:space="preserve">Thử việc</w:t></w:r></w:p><w:p><w:r><w:t>60 ngày</w:t>'
                   '</w:r></w:p></w:body></w:document>')
    assert review.extract_text("hd.DOCX", buf.getvalue()) == "Điều 1. Thử việc\n60 ngày"
    for name, data in (("a.docx", b"not a zip"), ("a.pdf", b"%PDF-broken"), ("a.txt", b"\xff\xfe\x00")):
        try:
            review.extract_text(name, data)
            raise AssertionError(name)
        except review.UnreadableDocument:
            pass


def test_review_clause_gates() -> None:
    chunk = {"payload": {"luat": "BLLĐ", "dieu": "Điều 26", "text": "Tiền lương thử việc ít nhất bằng 85%."}}
    calls, reply = [], ""
    orig = (review.retrieval.hybrid_search, review.reranker.rerank, review.llm._call_ollama)
    try:
        review.retrieval.hybrid_search = lambda q, top_k: [chunk]
        review.llm._call_ollama = lambda *a, **k: calls.append(1) or reply
        # Below the threshold: not judged, no LLM call.
        review.reranker.rerank = lambda q, c, top_k: [dict(chunk, rerank_score=0.01)]
        assert review.review_clause("Lương thử việc 70%.")["verdict"] == review.NO_PROVISION and not calls
        review.reranker.rerank = lambda q, c, top_k: [dict(chunk, rerank_score=0.9)]
        reply = '{"ket_luan": "trai_luat", "ly_do": "Trái Điều 26: ít nhất 85%."}'
        r = review.review_clause("Lương thử việc 70%.")
        assert r["verdict"] == "trai_luat" and r["citations"][0]["dieu"] == "Điều 26"
        # A conflict that names no Article is downgraded.
        reply = '{"ket_luan": "trai_luat", "ly_do": "Mức lương quá thấp."}'
        assert review.review_clause("Lương thử việc 70%.")["verdict"] == "can_luu_y"
        # A figure that's in neither the clause nor the law text: not trusted.
        reply = '{"ket_luan": "trai_luat", "ly_do": "Theo Điều 26, lương thử việc phải từ 13.000.000 đồng."}'
        r = review.review_clause("Lương thử việc 70%.")
        assert r["verdict"] == "can_luu_y" and r["reason"] == review.UNGROUNDED_REASON
        reply = '{"ket_luan": "trai_luat", "ly_do": "Điều 26 yêu cầu ít nhất 85%, điều khoản chỉ 70%."}'
        assert review.review_clause("Lương thử việc 70%.")["verdict"] == "trai_luat"
        assert review._numbers("02 ngày, 5.310.000 đồng, 1,5 lần") == {"2", "5310000", "15"}
        assert review._numbers("Điều 4, Khoản 3 của Nghị định 293/2025/NĐ-CP") == set()
        # A figure-bearing clause called illegal without the law's figure.
        reply = '{"ket_luan": "trai_luat", "ly_do": "Theo Điều 26, mức 70% không tuân theo quy định."}'
        assert review.review_clause("Lương thử việc 70%.")["verdict"] == "can_luu_y"
        # A list marker or a date is not a figure: an outright ban stays "trái luật".
        reply = '{"ket_luan": "trai_luat", "ly_do": "Điều 17 cấm giữ bản chính văn bằng của người lao động."}'
        assert review.review_clause("3. Từ ngày 01/11/2026, Công ty giữ bản chính văn bằng.")["verdict"] == "trai_luat"
        reply = '{"ket_luan": "phu_hop", "ly_do": "Phù hợp."}'
        assert review.review_clause("Lương thử việc 90%.")["citations"] == []
        reply = "not json"
        assert review.review_clause("Lương thử việc 90%.")["verdict"] == review.NO_PROVISION
    finally:
        review.retrieval.hybrid_search, review.reranker.rerank, review.llm._call_ollama = orig


if __name__ == "__main__":
    test_split_clauses()
    test_extract_text_docx_and_errors()
    test_review_clause_gates()
    test_is_refusal_only_on_leading_not_found()
    test_rrf_dedupes_on_luat_dieu_khoan()
    test_session_store_round_trips_citations()
    print("backend logic OK")
