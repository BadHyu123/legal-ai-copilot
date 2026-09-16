"""
Hybrid search: vector similarity + keyword/BM25, merged before
re-ranking (architecture doc, Section 3.9).

Why BM25 is in-memory (rank_bm25) instead of Qdrant's own full-text
index: Qdrant's text index is a boolean match filter (a chunk either
matches a keyword or it doesn't), not a ranked BM25 score, so it can't
be fused with vector scores by rank. This corpus is two laws — a few
hundred to low thousands of chunks — small enough that scrolling the
whole thing into memory once and scoring with rank_bm25 is simpler and
more correct than approximating BM25 out of Qdrant's filter. Revisit if
the corpus grows past roughly 10k chunks.
"""

import logging
import re
import time

from app.core.config import settings
from app.db import vector_store

logger = logging.getLogger(__name__)

_EMBED_MODEL = None

# In-memory BM25 corpus cache. Rebuilt lazily and on a TTL, rather than
# per-request, since scroll_all() + tokenizing the whole corpus is too
# slow to redo on every question.
_bm25_index = None
_bm25_corpus: list[dict] = []  # payload dicts, same order as _bm25_index's docs
_bm25_built_at: float = 0.0
_BM25_TTL_SECONDS = 15 * 60  # rebuild at most every 15 min; crawler runs are infrequent


def _get_embed_model():
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from sentence_transformers import SentenceTransformer
        # Must match the ingestion-time model exactly (crawler's
        # embedder.py) or vector search will be scoring against a
        # different embedding space.
        _EMBED_MODEL = SentenceTransformer(settings.embedding_model)
    return _EMBED_MODEL


def embed_query(question: str) -> list[float]:
    model = _get_embed_model()
    vector = model.encode([question], normalize_embeddings=True)[0]
    return vector.tolist()


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _ensure_bm25_index() -> None:
    global _bm25_index, _bm25_corpus, _bm25_built_at
    if _bm25_index is not None and (time.time() - _bm25_built_at) < _BM25_TTL_SECONDS:
        return

    from rank_bm25 import BM25Okapi

    points = vector_store.scroll_all()
    _bm25_corpus = [p["payload"] for p in points]
    tokenized = [_tokenize(p.get("text", "")) for p in _bm25_corpus]
    _bm25_index = BM25Okapi(tokenized) if tokenized else None
    _bm25_built_at = time.time()
    logger.info("BM25 index built over %d chunks", len(_bm25_corpus))


def _keyword_search(question: str, top_k: int) -> list[dict]:
    _ensure_bm25_index()
    if _bm25_index is None:
        return []
    scores = _bm25_index.get_scores(_tokenize(question))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [{"payload": _bm25_corpus[i], "score": float(scores[i])} for i in ranked if scores[i] > 0]


def _reciprocal_rank_fusion(result_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """Merge multiple ranked result lists into one, by RRF. Avoids having
    to normalize/compare cosine-similarity scores against BM25 scores
    directly, which aren't on the same scale.
    """
    scores: dict[str, float] = {}
    payload_by_key: dict[str, dict] = {}

    for results in result_lists:
        for rank, hit in enumerate(results):
            payload = hit["payload"]
            # Điều + Khoản uniquely identifies a chunk (matches embedder.py's point-id key).
            key = f"{payload.get('luat')}|{payload.get('dieu')}|{payload.get('khoan') or ''}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            payload_by_key[key] = payload

    ranked_keys = sorted(scores, key=lambda k_: scores[k_], reverse=True)
    return [{"payload": payload_by_key[k_], "rrf_score": scores[k_]} for k_ in ranked_keys]


def hybrid_search(question: str, top_k: int = 10) -> list[dict]:
    query_vector = embed_query(question)
    vector_hits = vector_store.search(query_vector, top_k=top_k)
    keyword_hits = _keyword_search(question, top_k=top_k)

    merged = _reciprocal_rank_fusion([vector_hits, keyword_hits])
    return merged[:top_k]
