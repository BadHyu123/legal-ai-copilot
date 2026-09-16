"""
Embeds chunks with vietnamese-sbert and upserts them into the Vector DB
(architecture doc, Section 3.7 / 4.1).

Wrapped behind this single module so the embedding model can be swapped
for a commercial API later (Section 4.3) without touching chunker.py or
the retrieval code in the backend.

NOT TESTED LIVE — this container has no network access, so neither the
sentence-transformers model download nor a real Qdrant connection could
be exercised here. The logic below is written carefully (idempotent
upserts, batching, dynamic vector-size detection) but treat the first
real run as the actual test; see the __main__ block for a self-contained
smoke test using Qdrant's in-memory mode (":memory:"), which needs no
running Qdrant server but still needs the real embedding model
downloaded, so it still needs network once, just not a Vector DB.
"""

import hashlib
import logging
import os
import uuid

logger = logging.getLogger(__name__)

VECTOR_DB_HOST = os.environ.get("VECTOR_DB_HOST", "vector-db")
VECTOR_DB_PORT = int(os.environ.get("VECTOR_DB_PORT", "6333"))
COLLECTION_NAME = os.environ.get("VECTOR_DB_COLLECTION", "legal_articles")
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "keepitreal/vietnamese-sbert")

# Deterministic namespace so point IDs are stable across runs (see
# _point_id below) — re-ingesting the same Điều/Khoản overwrites the
# same Qdrant point instead of creating a duplicate.
_ID_NAMESPACE = uuid.UUID("6f6a1e2e-2b8b-4b7a-9c1a-5a6b6c6d6e6f")

_model = None   # lazy-loaded SentenceTransformer instance
_client = None  # lazy-loaded Qdrant client


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model %s (first call — downloads on first run)",
                    EMBEDDING_MODEL_NAME)
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def _get_client(url: str | None = None):
    """`url` lets the __main__ smoke test pass ":memory:" without
    affecting the normal host/port-based connection used in production.
    """
    global _client
    if _client is None:
        from qdrant_client import QdrantClient
        if url:
            _client = QdrantClient(url)
        else:
            _client = QdrantClient(host=VECTOR_DB_HOST, port=VECTOR_DB_PORT)
    return _client


def _ensure_collection(client, vector_size: int) -> None:
    from qdrant_client.models import Distance, VectorParams

    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME in existing:
        return
    logger.info("Creating Qdrant collection %r (size=%d, cosine distance)",
                COLLECTION_NAME, vector_size)
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def _point_id(metadata) -> str:
    """Deterministic UUID from (luat, dieu, khoan) so re-embedding the
    same legal unit overwrites its existing point rather than
    duplicating it. Qdrant requires point IDs to be an unsigned int or a
    UUID string — uuid5 gives us the latter from arbitrary text.
    """
    key = f"{metadata.luat}|{metadata.dieu}|{metadata.khoan or ''}"
    return str(uuid.uuid5(_ID_NAMESPACE, key))


def embed_and_upsert(chunks: list, batch_size: int = 32, vector_db_url: str | None = None) -> None:
    """Embed a list of Chunk objects (from chunker.py) and upsert them
    into the Vector DB.

    The payload stores both `chunk.text` (so retrieval can return the
    passage directly without a second lookup) and every ChunkMetadata
    field, flattened, so the backend's filters can query on them
    directly (e.g. filter by `luat == "Bộ luật Lao động 2019"`).
    """
    if not chunks:
        logger.info("No chunks to embed — skipping")
        return

    from qdrant_client.models import PointStruct

    model = _get_model()
    client = _get_client(url=vector_db_url)
    vector_size = model.get_sentence_embedding_dimension()
    _ensure_collection(client, vector_size)

    total = len(chunks)
    for start in range(0, total, batch_size):
        batch = chunks[start:start + batch_size]
        texts = [c.text for c in batch]

        vectors = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,   # cosine distance expects unit vectors
            show_progress_bar=False,
        )

        points = []
        for chunk, vector in zip(batch, vectors):
            payload = {"text": chunk.text, **chunk.metadata.to_dict()}
            points.append(PointStruct(id=_point_id(chunk.metadata), vector=vector.tolist(), payload=payload))

        client.upsert(collection_name=COLLECTION_NAME, points=points)
        logger.info("Upserted %d/%d chunks", min(start + batch_size, total), total)


if __name__ == "__main__":
    # Self-contained smoke test — uses Qdrant's in-memory mode so no
    # running Qdrant server is needed, but still downloads the real
    # embedding model on first run (needs network once for that).
    #
    #   python -m crawler.embedder
    import logging as _logging
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1] / "shared"))
    from metadata_schema import ChunkMetadata  # noqa: E402
    from crawler.chunker import Chunk  # noqa: E402

    _logging.basicConfig(level=_logging.INFO)

    fake_chunks = [
        Chunk(
            text="Điều 1. Phạm vi điều chỉnh\n\nBộ luật Lao động quy định tiêu chuẩn lao động.",
            metadata=ChunkMetadata(luat="Bộ luật Lao động 2019", dieu="Điều 1",
                                    chu_de="Phạm vi điều chỉnh", khoan=None,
                                    source_url="https://example.com/test"),
        ),
    ]

    embed_and_upsert(fake_chunks, vector_db_url=":memory:")

    client = _get_client(url=":memory:")
    count = client.count(collection_name=COLLECTION_NAME).count
    print(f"Smoke test: {count} point(s) in collection {COLLECTION_NAME!r} after upsert")
