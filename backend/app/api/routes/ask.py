"""
/ask endpoint — orchestrates the full RAG flow (architecture doc,
Section 2.3):
  1. Load session history from the Session store
  1b. (query_rewrite) the LLM restates the question as one standalone
     question in legal terms, used to widen retrieval
  2. Hybrid search (vector + BM25) against the Vector DB
  3. Re-rank top-N -> top-3 with the bge-reranker cross-encoder
  4. If nothing relevant enough was found, return the out-of-scope
     fallback WITHOUT calling the LLM (Section 2.6 / 3.13) — this is a
     retrieval-side check on the reranked score, not something the LLM
     itself decides, so a bad retrieval can't be talked over by a
     confident-sounding hallucination.
  5. Otherwise build the prompt (history + re-ranked context + question)
     and call the LLM engine; if it answers that the context holds no
     relevant provision, return the fallback too (no misleading citations)
  6. Extract citations from the reranked context (the source of truth
     for citations is which chunks were actually retrieved, not
     regex-parsing them back out of the LLM's prose)
  7. Append the exchange to the Session store
"""

import logging
import re

from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import AskRequest, AskResponse, Citation
from app.services import llm, reranker, retrieval, session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ask"])

HYBRID_SEARCH_TOP_K = settings.rerank_candidates
RERANK_TOP_K = 3

# The system prompt makes the model say so when the context doesn't answer
# the question. Such an answer must not ship with citations: the retrieved
# chunks weren't relevant, and showing them reads as "the law says". Seen
# live: the 3B often leads in first ("Để trả lời câu hỏi này, tôi không tìm
# thấy quy định pháp luật nào..."), so the whole first sentence is checked.
_NOT_FOUND_RE = re.compile(r"không\s+(tìm thấy|có)\b.{0,40}?\b(quy định|căn cứ)", re.IGNORECASE)
_CITES_ARTICLE_RE = re.compile(r"Điều\s+\d")


def is_refusal(answer: str) -> bool:
    """A refusal says "not found" in its first sentence and cites no
    Article. "Không có quy định riêng về X, nhưng theo Điều 5..." is a
    (partial) answer, not a refusal."""
    first_sentence = re.split(r"(?<=[.!?])\s", answer.strip(), maxsplit=1)[0]
    return bool(_NOT_FOUND_RE.search(first_sentence)) and not _CITES_ARTICLE_RE.search(answer)

FALLBACK_MESSAGE = (
    "Không tìm thấy quy định pháp luật phù hợp trong phạm vi kiến thức hiện tại "
    "(Luật Lao động và Luật Thuế). Vui lòng thử diễn đạt lại câu hỏi hoặc tham khảo "
    "thêm nguồn khác."
)


def find_context(question: str, history: list[dict]) -> tuple[list[dict], list[dict]]:
    """Retrieve + rerank the legal context for a question; returns
    (hybrid-search candidates, reranked top-k). Shared with
    eval/run_eval.py so the eval measures exactly what /ask does."""
    previous = next((t["content"] for t in reversed(history) if t["role"] == "user"), None)
    standalone = llm.rewrite_query(question, previous) if settings.query_rewrite else ""

    # One query drives both hybrid search and the cross-encoder.
    if previous and standalone:
        # Follow-up made standalone by the LLM; a topic switch drops the old
        # topic instead of dragging it into retrieval.
        query = standalone
    elif previous:
        # No rewrite available: follow-ups ("còn trường hợp X thì sao?") carry
        # no legal terms of their own, so lean on the previous question.
        # ponytail: biases retrieval toward the old topic on a topic switch.
        query = f"{previous} {question}"
    elif standalone:
        # The user's words plus their legal restatement: scored on everyday
        # wording alone ("làm hỏng máy móc có phải đền tiền"), real
        # questions fell under the threshold.
        query = f"{question} {standalone}"
    else:
        query = question

    candidates = retrieval.hybrid_search(query, top_k=HYBRID_SEARCH_TOP_K)
    return candidates, reranker.rerank(query, candidates, top_k=RERANK_TOP_K)


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    history = session.load_history(request.session_id)
    _, reranked = find_context(request.question, history)

    if not reranked or reranked[0]["rerank_score"] < settings.rerank_relevance_threshold:
        logger.info("No sufficiently relevant context for question %r — returning fallback",
                    request.question)
        session.save_exchange(request.session_id, request.question, FALLBACK_MESSAGE,
                              {"is_fallback": True})
        return AskResponse(answer=FALLBACK_MESSAGE, citations=[], is_fallback=True)

    answer = llm.generate_answer(request.question, history, reranked)
    if is_refusal(answer):
        logger.info("LLM found the context irrelevant for %r — returning fallback", request.question)
        session.save_exchange(request.session_id, request.question, FALLBACK_MESSAGE,
                              {"is_fallback": True})
        return AskResponse(answer=FALLBACK_MESSAGE, citations=[], is_fallback=True)

    citations = [
        Citation(
            luat=c["payload"].get("luat", ""),
            dieu=c["payload"].get("dieu", ""),
            khoan=c["payload"].get("khoan"),
            text=c["payload"].get("text", ""),
            source_url=c["payload"].get("source_url"),
        )
        for c in reranked
    ]

    session.save_exchange(request.session_id, request.question, answer,
                          {"citations": [c.model_dump() for c in citations]})

    return AskResponse(answer=answer, citations=citations, is_fallback=False)
