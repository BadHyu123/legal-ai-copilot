"""
LLM engine call, behind a single interface so the engine can be a local
Ollama model or an external API without changing callers (architecture
doc, Section 2.1 / 4.3). Sprint 2 backlog item.

Also owns the anti-hallucination system prompt and out-of-scope
fallback logic (Section 3.12 / 3.13, Section 2.6).
"""

from app.core.config import settings

FALLBACK_NO_MATCH = "No matching legal provision was found."
FALLBACK_OUT_OF_SCOPE = "This question falls outside the current knowledge base (Labor Law and Tax Law only)."

ANTI_HALLUCINATION_SYSTEM_PROMPT = """You are a Vietnamese legal assistant. You may ONLY answer using the
provided legal context. You MUST cite the specific article and clause you
drew from. If the context does not contain a relevant provision, say so
explicitly instead of guessing."""


def generate_answer(question: str, history: list[dict], context_chunks: list[dict]) -> str:
    """
    TODO (Sprint 2):
      - Build the prompt: history slice + re-ranked context + question
        (in that order, per Section 3.11)
      - Call Ollama (settings.ollama_base_url) or the external API
        depending on settings.llm_provider
      - Retry once on timeout/error, per Section 2.6, before surfacing
        an error to the caller
    """
    raise NotImplementedError
