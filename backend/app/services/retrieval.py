"""
Hybrid search: vector similarity + keyword/BM25, merged before
re-ranking (architecture doc, Section 3.9). Sprint 2 backlog item.
"""

from app.db import vector_store


def hybrid_search(question: str, top_k: int = 10) -> list[dict]:
    """
    TODO (Sprint 2):
      - Embed `question` with the same model used at ingestion time
        (must match crawler/crawler/embedder.py's EMBEDDING_MODEL)
      - Run vector_store.search() for vector similarity candidates
      - Run a BM25 keyword search over the same collection
      - Merge + dedupe both result sets before returning top_k candidates
        for the reranker
    """
    raise NotImplementedError
