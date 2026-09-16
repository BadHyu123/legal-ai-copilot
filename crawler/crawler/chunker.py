"""
Semantic chunking by Điều (Article) / Khoản (Clause), per architecture
doc Section 3.1. Never split on a fixed word count — always split on the
document's own semantic boundaries so each chunk is a complete,
self-contained legal unit.

Rule of thumb (Section 3.1): one chunk per Article, or one chunk per
Clause when a single Article is unusually long.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "shared"))
from metadata_schema import ChunkMetadata  # noqa: E402


class Chunk:
    def __init__(self, text: str, metadata: "ChunkMetadata"):
        self.text = text
        self.metadata = metadata


def chunk_by_article(structured_document) -> list[Chunk]:
    """Split a StructuredDocument's Markdown into Article/Clause-level chunks.

    TODO (Sprint 1):
      - Walk the Markdown heading tree produced by parser.py
      - Emit one Chunk per Article by default
      - If an Article's text exceeds a length threshold, split further
        by Clause (Khoản) instead — never split mid-clause
      - Populate ChunkMetadata (luat, dieu, chu_de, khoan) for every chunk
        from the doc's headings, matching shared/metadata_schema.py exactly
    """
    raise NotImplementedError
