"""
Entry point for the Law crawler batch job (architecture doc, Section 2.1 & 5).

Run as: docker-compose --profile crawler run law-crawler
Or locally: python -m crawler.main

Sprint 1 backlog this file wires together:
  1. Fetch the curated document list from luatvietnam.vn
     (sources/luatvietnam.py) — primary text source; see that module for
     why it replaced thuvienphapluat.vn
  1b. Cross-check each document against vanban.chinhphu.vn's official
      registry (sources/vanban_chinhphu.py) — see that module's docstring
      for exactly what this can and can't confirm (no repeal-status field
      there, only registry presence + effective date).
  2. Hash-based change detection (change_detection.py)
  3. Parse to structured Markdown (parser.py)
  4. Semantic chunk by Điều/Khoản (chunker.py)
  5. Embed with vietnamese-sbert and upsert to Vector DB (embedder.py)
"""

import logging

import httpx

from crawler.sources import luatvietnam, vanban_chinhphu
from crawler import change_detection, parser, chunker, embedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crawler")


def run() -> None:
    logger.info("Starting law crawler run")

    documents = luatvietnam.list_documents()

    # Cross-check each document against the Government's own registry.
    # This doesn't change what gets ingested; it's a corroboration signal
    # logged for now. TODO (Sprint 1/2): decide what should happen on a
    # mismatch — e.g. flag for manual review rather than silently ingest.
    try:
        cross_checks = vanban_chinhphu.check_effective_status([d.so_hieu for d in documents])
    except httpx.HTTPError as e:
        logger.warning("Government registry cross-check skipped: %s", e)
        cross_checks = {}
    for doc in documents:
        so_hieu = doc.so_hieu
        cross_check = cross_checks.get(so_hieu)
        if cross_check is None:
            continue
        if not cross_check.found:
            logger.warning("%s (%s) not found in Government registry: %s",
                            doc.law_name, so_hieu, cross_check.note)
        else:
            logger.info("%s (%s) confirmed in Government registry, hiệu lực từ %s",
                         doc.law_name, so_hieu, cross_check.ngay_hieu_luc)

    # TODO (Sprint 1): skip documents whose hash hasn't changed
    changed_documents = change_detection.filter_changed(documents)
    logger.info("%d/%d documents changed since last run", len(changed_documents), len(documents))

    for doc in changed_documents:
        # TODO (Sprint 1): parse -> structured Markdown, preserving heading hierarchy
        structured = parser.parse_to_markdown(doc)

        # TODO (Sprint 1): chunk by Article/Clause, attach ChunkMetadata
        chunks = chunker.chunk_by_article(structured)
        document_hash = change_detection.hash_of(doc)
        for chunk in chunks:
            chunk.metadata.document_hash = document_hash

        # TODO (Sprint 1): embed + upsert into Vector DB
        embedder.embed_and_upsert(chunks)

        # TODO (Sprint 1): persist the new hash so next run can skip this doc
        change_detection.mark_ingested(doc)

    logger.info("Crawler run complete")


if __name__ == "__main__":
    run()
