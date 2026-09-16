"""
Thin interface over the Vector DB client, so retrieval.py never talks to
Qdrant/ChromaDB directly (architecture doc Section 4.3 — swap-ability by
design). The crawler writes to this same collection independently
(crawler/crawler/embedder.py); this module only reads.
"""

from app.core.config import settings


def search(query_embedding: list[float], top_k: int = 10) -> list[dict]:
    """Vector similarity search. Returns raw hits with payload metadata.

    TODO (Sprint 2): implement using qdrant_client against
    settings.vector_db_host / settings.vector_db_collection.
    """
    raise NotImplementedError
