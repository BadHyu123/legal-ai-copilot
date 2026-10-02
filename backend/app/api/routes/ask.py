"""
/ask endpoint — orchestrates the full RAG flow (architecture doc,
Section 2.3):
  1. Load session history from the Session store
  2. Hybrid search (vector + BM25) against the Vector DB
  3. Re-rank top-N -> top-3 with bge-reranker
  4. If nothing relevant enough was found, return the out-of-scope
     fallback WITHOUT calling the LLM (Section 2.6 / 3.13) — this is a
     retrieval-side check on the reranked score, not something the LLM
     itself decides, so a bad retrieval can't be talked over by a
     confident-sounding hallucination.
  5. Otherwise build the prompt (history + re-ranked context + question)
     and call the LLM engine
  6. Extract citations from the reranked context (the source of truth
     for citations is which chunks were actually retrieved, not
     regex-parsing them back out of the LLM's prose)
  7. Append the exchange to the Session store
"""

import logging

from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import AskRequest, AskResponse, Citation
from app.services import llm, reranker, retrieval, session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ask"])

HYBRID_SEARCH_TOP_K = 10
RERANK_TOP_K = 3

FALLBACK_MESSAGE = (
    "Không tìm thấy quy định pháp luật phù hợp trong phạm vi kiến thức hiện tại "
    "(Luật Lao động và Luật Thuế). Vui lòng thử diễn đạt lại câu hỏi hoặc tham khảo "
    "thêm nguồn khác."
)


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    history = session.load_history(request.session_id)

    # Follow-ups ("còn trường hợp X thì sao?") carry no legal terms of their
    # own, so retrieval also sees the previous question.
    # ponytail: biases retrieval toward the old topic when the user switches
    # topics; swap for an LLM query rewrite if the eval set shows it hurts.
    previous = [t["content"] for t in history if t["role"] == "user"]
    retrieval_query = f"{previous[-1]} {request.question}" if previous else request.question

    candidates = retrieval.hybrid_search(retrieval_query, top_k=HYBRID_SEARCH_TOP_K)
    reranked = reranker.rerank(retrieval_query, candidates, top_k=RERANK_TOP_K)

    if not reranked or reranked[0]["rerank_score"] < settings.rerank_relevance_threshold:
        logger.info("No sufficiently relevant context for question %r — returning fallback",
                    request.question)
        session.save_exchange(request.session_id, request.question, FALLBACK_MESSAGE,
                              {"is_fallback": True})
        return AskResponse(answer=FALLBACK_MESSAGE, citations=[], is_fallback=True)

    answer = llm.generate_answer(request.question, history, reranked)

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
