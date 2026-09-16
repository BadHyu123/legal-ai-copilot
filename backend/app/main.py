"""
FastAPI entry point — the single client-facing entry point for the
system (architecture doc, Section 2.1). Owns RAG orchestration and
session management; the only component talking to the Vector DB,
Session store, and LLM engine.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, ask, sessions
from app.db import session_store

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
