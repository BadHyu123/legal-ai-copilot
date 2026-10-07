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
- Nếu phần căn cứ không đủ để trả lời câu hỏi, PHẢI nói rõ là không tìm thấy quy định phù hợp, không được đoán.
- Câu đầu tiên trả lời thẳng vào câu hỏi bằng nội dung cụ thể từ căn cứ (con số, thời hạn, điều kiện, trường hợp), không mở đầu bằng câu dẫn dắt như "Để trả lời câu hỏi này". Không nhắc lại cùng một ý hai lần."""

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


def _call_ollama(prompt: str, system: str = ANTI_HALLUCINATION_SYSTEM_PROMPT,
                 max_tokens: int = -1, timeout: float = 60.0,
                 examples: tuple[tuple[str, str], ...] = (), fmt: dict | None = None) -> str:
    """`examples` are few-shot (user, assistant) turns placed before the
    prompt; `fmt` is a JSON schema the reply must follow (Ollama structured
    output)."""
    shots = [{"role": role, "content": text}
             for user, assistant in examples
             for role, text in (("user", user), ("assistant", assistant))]
    resp = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": [{"role": "system", "content": system}, *shots,
                         {"role": "user", "content": prompt}],
            "stream": False,
            # Ollama's default context (2-4k tokens) silently truncates from
            # the start once history + 3 chunks overflow it — which drops
            # the anti-hallucination system prompt first.
            "options": {"num_ctx": 8192, "temperature": 0, "num_predict": max_tokens},
            **({"format": fmt} if fmt else {}),
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


QUERY_REWRITE_PROMPT = """Bạn viết lại câu hỏi của người dân thành MỘT câu hỏi tương đương, dùng đúng thuật ngữ trong văn bản pháp luật Việt Nam (ví dụ "công ty" -> "người sử dụng lao động", "nhân viên" -> "người lao động").
Nếu có câu hỏi trước, chỉ dùng nó để hiểu câu hỏi hiện tại khi câu hiện tại là câu hỏi nối tiếp; nếu câu hiện tại là chủ đề mới thì bỏ qua câu trước.
Giữ nguyên ý hỏi. KHÔNG trả lời, KHÔNG nêu con số hay số Điều. Chỉ viết bằng tiếng Việt."""

# Topics deliberately absent from eval/questions*.jsonl, so the examples
# can't leak answers into the evaluation.
_REWRITE_EXAMPLES = (
    ("Công ty không đóng bảo hiểm cho tôi thì sao?",
     "Người sử dụng lao động không tham gia bảo hiểm xã hội bắt buộc cho người lao động thì bị xử lý thế nào?"),
    ("Mua xe ô tô có phải chịu thuế giá trị gia tăng không?",
     "Hàng hóa là xe ô tô có thuộc đối tượng chịu thuế giá trị gia tăng không?"),
    ("Câu hỏi trước: Lao động nữ sinh con được nghỉ bao lâu?\nCâu hỏi hiện tại: Còn chồng thì sao?",
     "Lao động nam được nghỉ việc hưởng chế độ thai sản khi vợ sinh con trong bao lâu?"),
    ("Câu hỏi trước: Công ty có phải đóng bảo hiểm thất nghiệp cho tôi không?\nCâu hỏi hiện tại: Đăng ký kết hôn cần giấy tờ gì?",
     "Đăng ký kết hôn cần những giấy tờ gì?"),
)
_NON_VIETNAMESE = re.compile(r"[⺀-鿿가-힯]+")  # CJK / Hangul leaking from the model


def rewrite_query(question: str, previous: str | None = None) -> str:
    """One standalone question in legal terminology, used for retrieval.
    With `previous`, a follow-up ("còn chồng thì sao?") becomes standalone
    and a topic switch drops the old topic. Returns "" on any failure, so a
    slow or down LLM never blocks retrieval."""
    if settings.llm_provider != "ollama":
        return ""
    prompt = f"Câu hỏi trước: {previous}\nCâu hỏi hiện tại: {question}" if previous else question
    try:
        text = _call_ollama(prompt, system=QUERY_REWRITE_PROMPT, max_tokens=80, timeout=15.0,
                            examples=_REWRITE_EXAMPLES)
    except httpx.HTTPError as e:
        logger.warning("Query rewrite failed (%s) — retrieving with the original question", e)
        return ""
    return _NON_VIETNAMESE.sub("", text.strip().splitlines()[0] if text.strip() else "").strip()


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
