"""
Cross-encoder re-ranking with bge-reranker: narrows the hybrid search
candidates down to the top-k most relevant (architecture doc, Section
3.10). A cross-encoder scores (question, chunk) pairs jointly, which is
slower but more accurate than the bi-encoder similarity used for the
initial vector search — hence: cast a wide net first, then re-rank down.
"""

from app.core.config import settings

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(settings.reranker_model)
    return _reranker


def rerank(question: str, candidates: list[dict], top_k: int = 3) -> list[dict]:
    """`candidates` are dicts with a "payload" key holding {text, luat,
    dieu, khoan, chu_de, source_url}, as produced by retrieval.hybrid_search().
    Returns the top_k candidates, each with an added "rerank_score" key.
    """
    if not candidates:
        return []

    model = _get_reranker()
    pairs = [(question, c["payload"].get("text", "")) for c in candidates]
    scores = model.predict(pairs)

    scored = list(zip(candidates, scores))
    scored.sort(key=lambda pair: pair[1], reverse=True)

    top = scored[:top_k]
    results = []
    for candidate, score in top:
        enriched = dict(candidate)
        enriched["rerank_score"] = float(score)
        results.append(enriched)
    return results
