"""
Contract review (architecture doc, Section 2.4): split an uploaded
contract into clauses, retrieve the provisions each clause touches with
the same hybrid search + rerank as /ask, and have the LLM say whether the
clause conflicts with them.

Same anti-hallucination rules as /ask: a clause with no relevant
provision above the (review) rerank threshold is never sent to the LLM;
citations come from the retrieved chunks. On top of that, a verdict is
downgraded to "cần lưu ý" when it isn't grounded: "trái luật" must name an
Article; every figure in the reason must appear in the clause or the
retrieved text (otherwise the reason is replaced too); and a clause with
figures is "trái luật" only if the reason quotes a figure from the law.
"""

import io
import json
import logging
import re
import zipfile

from app.services import llm, reranker, retrieval

logger = logging.getLogger(__name__)

MAX_CLAUSES = 40
MAX_CLAUSE_CHARS = 1200
MIN_CLAUSE_CHARS = 30
# Fewer candidates than /ask: the CPU reranker is the cost per clause
# (~0.3 s a pair), and a clause is long, specific text, so the right
# Article is near the top of hybrid search already.
REVIEW_CANDIDATES = 10
REVIEW_TOP_K = 3
# The cross-encoder scores question/passage pairs; a bare clause is a
# statement, and scored low even against the Article it breaks (Điều 17 vs
# "phải đặt cọc 5 triệu": 0.11). Asked as a question it scores 0.36, while
# non-legal lines (party details) stay under 0.05. So review has its own
# threshold, picked on eval/contract_clauses.jsonl (2026-10-03).
RERANK_QUERY = "Pháp luật lao động quy định thế nào về nội dung sau: {clause}"
REVIEW_RELEVANCE_THRESHOLD = 0.15

VERDICTS = ("trai_luat", "can_luu_y", "phu_hop")
NO_PROVISION = "khong_doi_chieu"  # nothing relevant retrieved: not judged


class UnreadableDocument(ValueError):
    """Shown to the user as is (Vietnamese)."""


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:  # pypdf raises many types on malformed files
            raise UnreadableDocument("Không đọc được tệp PDF này.") from e
        if len(text.strip()) < MIN_CLAUSE_CHARS:
            raise UnreadableDocument("PDF không có lớp chữ (bản scan). Hãy dán nội dung hợp đồng vào ô văn bản.")
        return text
    if name.endswith(".docx"):
        # A .docx is a zip; paragraphs are <w:p>, text runs <w:t>. Enough
        # for contract text without pulling in python-docx.
        try:
            xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
        except (zipfile.BadZipFile, KeyError) as e:
            raise UnreadableDocument("Không đọc được tệp Word này (chỉ hỗ trợ .docx).") from e
        paragraphs = re.findall(r"<w:p[ >].*?</w:p>", xml, re.DOTALL)
        return "\n".join("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)) for p in paragraphs)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise UnreadableDocument("Chỉ hỗ trợ tệp PDF, Word (.docx) hoặc văn bản thuần (.txt).") from e


# Clause headings, most to least specific. The first style that occurs at
# least twice is the one the contract uses.
_HEADING_STYLES = (
    re.compile(r"^Điều\s+\d+\b", re.IGNORECASE),
    re.compile(r"^[IVX]+\s*[.)]\s"),
    re.compile(r"^\d{1,2}\s*[.)]\s"),
)


def split_clauses(text: str) -> list[str]:
    """Contract text -> clauses (one per Điều / numbered heading, or one
    per paragraph when there are none). The preamble before the first
    heading (title, parties' details) is dropped. Long clauses are cut at
    line boundaries, each part keeping the clause's heading line."""
    lines = [" ".join(l.split()) for l in text.splitlines()]
    lines = [l for l in lines if l]
    style = next((s for s in _HEADING_STYLES if sum(bool(s.match(l)) for l in lines) >= 2), None)

    blocks: list[list[str]] = []
    if style is None:
        blocks = [[l] for l in lines]
    else:
        for line in lines:
            if style.match(line):
                blocks.append([line])
            elif blocks:
                blocks[-1].append(line)

    clauses: list[str] = []
    for block in blocks:
        heading, parts, current = block[0], [], block[0]
        for line in block[1:]:
            if len(current) + len(line) > MAX_CLAUSE_CHARS:
                parts.append(current)
                current = f"{heading}\n{line}"
            else:
                current += f"\n{line}"
        parts.append(current)
        clauses += [p for p in parts if len(p) >= MIN_CLAUSE_CHARS]
    return clauses


REVIEW_SYSTEM_PROMPT = """Bạn là luật sư rà soát hợp đồng theo pháp luật Việt Nam. Đối chiếu ĐIỀU KHOẢN HỢP ĐỒNG với CĂN CỨ PHÁP LÝ được cung cấp và chọn "ket_luan":
- "trai_luat": điều khoản trái với một quy định cụ thể trong căn cứ (ví dụ thấp hơn mức tối thiểu, vượt mức tối đa, thuộc hành vi bị cấm, bỏ một quyền mà luật bảo đảm).
- "can_luu_y": không rõ trái luật nhưng mơ hồ, thiếu nội dung bắt buộc hoặc bất lợi rõ rệt cho một bên.
- "phu_hop": phù hợp với căn cứ, hoặc căn cứ không quy định về nội dung này.
Cách đối chiếu:
- Mức bằng đúng giới hạn của luật là phù hợp (luật cho "không quá 48 giờ/tuần" thì 48 giờ/tuần là phù hợp; luật yêu cầu "ít nhất 30 ngày" thì 30 ngày là phù hợp).
- Chỉ áp dụng quy định đúng trường hợp của điều khoản (đúng loại hợp đồng, đúng đối tượng, đúng bên); nếu căn cứ quy định cho trường hợp khác thì không dùng để kết luận trái luật.
Chỉ dựa vào căn cứ được cung cấp, không dùng hiểu biết bên ngoài. Nếu không chắc thì chọn "phu_hop".
Trả lời theo thứ tự:
"quy_dinh": quy định trong căn cứ áp dụng cho điều khoản (Điều nào, con số hoặc điều kiện gì); để trống nếu không có.
"so_sanh": so sánh con số hoặc điều kiện của điều khoản với quy định đó (lớn hơn, nhỏ hơn, bằng, trái hay không).
"ket_luan": theo kết quả so sánh.
"ly_do": 1-2 câu tiếng Việt cho người đọc; với "trai_luat" phải nêu Điều cụ thể và con số hoặc điều kiện trong căn cứ."""

# Field order matters: the 3B writes the rule and the comparison before it
# commits to a verdict. Asked for the verdict first, it called "08 ngày
# phép" compliant while quoting "12 ngày" in its own reason.
_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {"quy_dinh": {"type": "string"},
                   "so_sanh": {"type": "string"},
                   "ket_luan": {"type": "string", "enum": list(VERDICTS)},
                   "ly_do": {"type": "string"}},
    "required": ["quy_dinh", "so_sanh", "ket_luan", "ly_do"],
}
_CITES_ARTICLE_RE = re.compile(r"Điều\s+\d")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
UNGROUNDED_REASON = "Cần đối chiếu thêm điều khoản này với các quy định dưới đây."


# Article/clause references and document numbers ("Điều 4, Khoản 3",
# "293/2025/NĐ-CP") aren't figures being compared.
_REFERENCE_RE = re.compile(r"(?:Điều|Khoản|khoản|điểm|Điểm)\s+\d+\w*|\d+/\d{4}/[\w-]+")
# Nor are a clause's own list markers ("3. ", "II) ") and dates: a clause
# like "3. Công ty giữ bản chính văn bằng" has no figure to compare.
_MARKER_OR_DATE_RE = re.compile(r"(?m)^\s*(?:\d{1,2}|[IVX]+)\s*[.)]\s|\b\d{1,2}/\d{1,2}/\d{4}\b")


def _numbers(text: str) -> set[str]:
    """Figures as written in Vietnamese ("13.000.000", "02", "1,5"),
    normalized so "02" == "2" and "5.310.000" == "5310000"."""
    text = _REFERENCE_RE.sub(" ", text)
    return {re.sub(r"[.,]", "", n).lstrip("0") or "0" for n in _NUMBER_RE.findall(text)}


def _ungrounded_numbers(reason: str, source: str) -> set[str]:
    """Numbers the reason states that neither the clause nor the retrieved
    provisions contain. Seen live: "không được thấp hơn 13.000.000
    đồng/tháng" against a minimum-wage table topping out at 5.310.000."""
    return _numbers(reason) - _numbers(source)


def _citation(chunk: dict) -> dict:
    p = chunk["payload"]
    return {"luat": p.get("luat", ""), "dieu": p.get("dieu", ""), "khoan": p.get("khoan"),
            "text": p.get("text", ""), "source_url": p.get("source_url")}


def review_clause(clause: str) -> dict:
    candidates = retrieval.hybrid_search(clause, top_k=REVIEW_CANDIDATES)
    relevant = [c for c in reranker.rerank(RERANK_QUERY.format(clause=clause), candidates, top_k=REVIEW_TOP_K)
                if c["rerank_score"] >= REVIEW_RELEVANCE_THRESHOLD]
    if not relevant:
        return {"clause": clause, "verdict": NO_PROVISION, "reason": "", "citations": []}

    context = "\n\n".join(
        f"[{c['payload'].get('dieu')}{', ' + c['payload']['khoan'] if c['payload'].get('khoan') else ''}"
        f" - {c['payload'].get('luat')}]\n{c['payload'].get('text', '')}" for c in relevant)
    prompt = f"CĂN CỨ PHÁP LÝ:\n{context}\n\nĐIỀU KHOẢN HỢP ĐỒNG:\n{clause}"
    try:
        result = json.loads(llm._call_ollama(prompt, system=REVIEW_SYSTEM_PROMPT, fmt=_REVIEW_SCHEMA, max_tokens=500))
        verdict, reason = result["ket_luan"], result["ly_do"].strip()
    except Exception as e:  # LLM down or malformed JSON: report the clause as not judged
        logger.warning("Review LLM call failed for a clause: %s", e)
        return {"clause": clause, "verdict": NO_PROVISION, "reason": "", "citations": []}
    if verdict not in VERDICTS:
        verdict = "can_luu_y"
    if verdict == "trai_luat" and not _CITES_ARTICLE_RE.search(reason):
        # A conflict claim that names no Article isn't grounded enough to
        # tell a user "this is illegal".
        verdict = "can_luu_y"
    if verdict != "phu_hop" and _ungrounded_numbers(reason, prompt):
        # The reason rests on a figure that isn't in the law text: don't
        # show it, and don't call the clause illegal on its strength.
        logger.info("Review reason has numbers absent from the context: %r", reason)
        verdict, reason = "can_luu_y", UNGROUNDED_REASON
    figures = _numbers(_MARKER_OR_DATE_RE.sub(" ", clause))
    if verdict == "trai_luat" and figures and not (_numbers(reason) - figures):
        # A clause with figures is illegal only against a legal figure; seen
        # live: "12.000.000 đồng/tháng không tuân theo quy định" with no
        # minimum wage quoted (the table wasn't in the retrieved context).
        verdict = "can_luu_y"
    citations = [_citation(c) for c in relevant] if verdict != "phu_hop" else []
    return {"clause": clause, "verdict": verdict, "reason": reason, "citations": citations}
