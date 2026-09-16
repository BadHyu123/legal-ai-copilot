"""
Embeds chunks with vietnamese-sbert and upserts them into the Vector DB
(architecture doc, Section 3.7 / 4.1).

Wrapped behind this single module so the embedding model can be swapped
for a commercial API later (Section 4.3) without touching chunker.py or
the retrieval code in the backend.
"""

import os

VECTOR_DB_HOST = os.environ.get("VECTOR_DB_HOST", "vector-db")
VECTOR_DB_PORT = int(os.environ.get("VECTOR_DB_PORT", "6333"))
COLLECTION_NAME = os.environ.get("VECTOR_DB_COLLECTION", "legal_articles")
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "keepitreal/vietnamese-sbert")

_model = None  # lazy-loaded SentenceTransformer instance
_client = None  # lazy-loaded Qdrant client


def _get_model():
    global _model
    if _model is None:
        # TODO (Sprint 1): from sentence_transformers import SentenceTransformer
        # _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        raise NotImplementedError
    return _model


def _get_client():
    global _client
    if _client is None:
        # TODO (Sprint 1): from qdrant_client import QdrantClient
        # _client = QdrantClient(host=VECTOR_DB_HOST, port=VECTOR_DB_PORT)
        # Ensure COLLECTION_NAME exists with the right vector size before upserting.
        raise NotImplementedError
    return _client


def embed_and_upsert(chunks: list) -> None:
    """Embed a list of Chunk objects and upsert them into the Vector DB.

    TODO (Sprint 1):
      - Embed chunk.text for every chunk in the batch
      - Upsert (id, vector, payload=chunk.metadata.to_dict()) into
        COLLECTION_NAME — payload keys must match shared/metadata_schema.py
        exactly since the backend's retrieval filters key off them directly
    """
    raise NotImplementedError
