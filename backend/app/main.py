"""
FastAPI entry point — the single client-facing entry point for the
system (architecture doc, Section 2.1). Owns RAG orchestration and
session management; the only component talking to the Vector DB,
Session store, and LLM engine.
"""

from fastapi import FastAPI

from app.api.routes import health, ask

app = FastAPI(title="Legal AI Copilot API")

app.include_router(health.router)
app.include_router(ask.router)
