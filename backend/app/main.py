"""
FastAPI entry point — the single client-facing entry point for the
system (architecture doc, Section 2.1). Owns RAG orchestration and
session management; the only component talking to the Vector DB,
Session store, and LLM engine.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, ask, sessions
from app.db import session_store
from app.services import reranker, retrieval

logger = logging.getLogger(__name__)
app = FastAPI(title="Legal AI Copilot API")

app.add_middleware(
    CORSMiddleware,
    # Local-first, single-user tool — wide open for localhost dev is fine.
    # Tighten this before ever exposing the backend beyond localhost.
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ask.router)
app.include_router(sessions.router)


@app.on_event("startup")
def on_startup() -> None:
    session_store.init_db()

    # Load models and build the BM25 index now instead of on the first
    # /ask. Best-effort: the app must still start when a model can't
    # download or Qdrant has no collection yet — the lazy getters retry.
    warmups = (
        lambda: reranker.rerank("khởi động", [{"payload": {"text": "khởi động"}}]),
        lambda: retrieval.hybrid_search("khởi động"),
    )
    for warmup in warmups:
        try:
            warmup()
        except Exception:
            logger.exception("Warmup failed — will retry lazily on first /ask")
