"""
LLM engine call, behind a single interface so the engine can be a local
Ollama model or an external API without changing callers (architecture
doc, Section 2.1 / 4.3).

Also owns the anti-hallucination system prompt (Section 3.12) and
citation-format validation on the response (Section 3.14) — the /ask
route decides what to do when a question has no good context at all
(Section 2.6 / 3.13); this module's job is just "given context, answer
faithfully and cite it".
"""

import logging
import re

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ANTI_HALLUCINATION_SYSTEM_PROMPT = """Bạn là trợ lý pháp lý AI, chỉ trả lời dựa trên phần "Căn cứ pháp lý" được cung cấp dưới đây.
Quy tắc bắt buộc:
- KHÔNG được bịa hoặc suy diễn quy định pháp luật không có trong phần căn cứ.
- MỌI câu trả lời phải trích dẫn cụ thể Điều/Khoản đã dùng, theo định dạng (Điều X, Khoản Y - Tên luật).
- Nếu phần căn cứ không đủ để trả lời câu hỏi, PHẢI nói rõ là không tìm thấy quy định phù hợp, không được đoán."""

CITATION_RE = re.compile(r"Điều\s+\d+")


def _build_prompt(question: str, history: list[dict], context_chunks: list[dict]) -> str:
    context_block = "\n\n".join(
        f"[{c['payload'].get('dieu')}"
        f"{', ' + c['payload'].get('khoan') if c['payload'].get('khoan') else ''} "
        f"- {c['payload'].get('luat')}]\n{c['payload'].get('text', '')}"
        for c in context_chunks
    )

    # Keep history short — a handful of prior turns is enough for
    # follow-up questions ("còn về trường hợp X thì sao?") without
    # ballooning the prompt. Sprint 3 decides the exact turn limit when
    # session history is wired in for real.
    history_block = "\n".join(
        f"{turn['role']}: {turn['content']}" for turn in history[-6:]
    )

    parts = []
    if history_block:
        parts.append(f"Lịch sử hội thoại:\n{history_block}")
    parts.append(f"Căn cứ pháp lý:\n{context_block}")
    parts.append(f"Câu hỏi: {question}")
    return "\n\n".join(parts)


def _call_ollama(prompt: str) -> str:
    resp = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": ANTI_HALLUCINATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _call_external_api(prompt: str) -> str:
    """Placeholder for a commercial API fallback (architecture doc,
    Section 4.3's swap-ability). Not needed for the local-first default
    path — implement when/if EXTERNAL_LLM_API_KEY is actually used.
    """
    raise NotImplementedError("Set LLM_PROVIDER=ollama, or implement this for your chosen API")


def generate_answer(question: str, history: list[dict], context_chunks: list[dict]) -> str:
    prompt = _build_prompt(question, history, context_chunks)

    call = _call_ollama if settings.llm_provider == "ollama" else _call_external_api

    try:
        answer = call(prompt)
    except (httpx.TimeoutException, httpx.HTTPError) as e:
        logger.warning("LLM call failed (%s), retrying once", e)
        answer = call(prompt)  # one retry, per Section 2.6; let a second failure raise

    if context_chunks and not CITATION_RE.search(answer):
        logger.warning(
            "LLM answer has no 'Điều N' citation despite context being provided — "
            "the prompt's citation rule may need strengthening, or the model may "
            "need a stricter one (see architecture doc Section 3.14)."
        )

    return answer
