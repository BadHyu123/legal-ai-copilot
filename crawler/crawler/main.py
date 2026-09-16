"""
Entry point for the Law crawler batch job (architecture doc, Section 2.1 & 5).

Run as: docker-compose --profile crawler run law-crawler
Or locally: python -m crawler.main

Sprint 1 backlog this file wires together:
  1. Crawl thuvienphapluat.vn + vanban.chinhphu.vn (sources/)
  2. Hash-based change detection (change_detection.py)
  3. Parse to structured Markdown (parser.py)
  4. Semantic chunk by Điều/Khoản (chunker.py)
  5. Embed with vietnamese-sbert and upsert to Vector DB (embedder.py)
"""

import logging

from crawler.sources import thuvienphapluat, vanban_chinhphu
from crawler import change_detection, parser, chunker, embedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crawler")


def run() -> None:
    logger.info("Starting law crawler run")

    # TODO (Sprint 1): fetch listing pages from both sources
    documents = []
    documents += thuvienphapluat.list_documents()
    documents += vanban_chinhphu.list_documents()

    # TODO (Sprint 1): skip documents whose hash hasn't changed
    changed_documents = change_detection.filter_changed(documents)
    logger.info("%d/%d documents changed since last run", len(changed_documents), len(documents))

    for doc in changed_documents:
        # TODO (Sprint 1): parse -> structured Markdown, preserving heading hierarchy
        structured = parser.parse_to_markdown(doc)

        # TODO (Sprint 1): chunk by Article/Clause, attach ChunkMetadata
        chunks = chunker.chunk_by_article(structured)

        # TODO (Sprint 1): embed + upsert into Vector DB
        embedder.embed_and_upsert(chunks)

        # TODO (Sprint 1): persist the new hash so next run can skip this doc
        change_detection.mark_ingested(doc)

    logger.info("Crawler run complete")


if __name__ == "__main__":
    run()
