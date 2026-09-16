"""
/ask endpoint — Sprint 2 backlog item, stubbed now so the route shape
and request/response contract are settled before the RAG logic behind
it is implemented.

Full flow this will orchestrate (architecture doc, Section 2.3):
  1. Load session history from the Session store
  2. Hybrid search (vector + BM25) against the Vector DB
  3. Re-rank top-10 -> top-3 with bge-reranker
  4. Build prompt (history + re-ranked context + question)
  5. Call the LLM engine
  6. Validate citation format on the response
  7. Append the exchange to the Session store
"""

from fastapi import APIRouter

from app.models.schemas import AskRequest, AskResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    # TODO (Sprint 2): implement the pipeline described above using
    # app/services/{session,retrieval,reranker,llm}.py
    raise NotImplementedError("Implemented in Sprint 2")
