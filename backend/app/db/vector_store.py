"""
Thin interface over the Vector DB client (architecture doc, Section 4.3
— swap-ability by design). Two read paths:
  - search(): real vector similarity search
  - scroll_all(): pulls every point's payload, used by retrieval.py to
    build an in-memory BM25 index (see that module for why — Qdrant's
    own full-text index is a boolean match, not a ranked BM25 score).
"""

from app.core.config import settings

_client = None


def _get_client():
    global _client
    if _client is None:
        from qdrant_client import QdrantClient
        _client = QdrantClient(host=settings.vector_db_host, port=settings.vector_db_port)
    return _client


def search(query_embedding: list[float], top_k: int = 10) -> list[dict]:
    """Vector similarity search. Returns [{id, score, payload}, ...]."""
    client = _get_client()
    hits = client.search(
        collection_name=settings.vector_db_collection,
        query_vector=query_embedding,
        limit=top_k,
    )
    return [{"id": h.id, "score": h.score, "payload": h.payload} for h in hits]


def scroll_all(batch_size: int = 256) -> list[dict]:
    """Pull every point's id + payload. Fine at this corpus size (two
    laws, low thousands of chunks at most) — would need a real BM25
    service instead of in-memory rank_bm25 if the corpus grows much
    beyond that (see retrieval.py).
    """
    client = _get_client()
    all_points: list[dict] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.vector_db_collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        all_points.extend({"id": p.id, "payload": p.payload} for p in points)
        if offset is None:
            break
    return all_points
