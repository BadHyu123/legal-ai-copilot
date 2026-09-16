"""
Parses raw crawled documents into structured Markdown that preserves
heading hierarchy (Chapter -> Section -> Article -> Clause -> Point),
per architecture doc Section 3.3.

The chunker (chunker.py) depends on this hierarchy being intact, so
whatever library is chosen here (LlamaParse or Unstructured) must be
configured to keep headings as headings, not flatten them to plain text.
"""

from dataclasses import dataclass


@dataclass
class StructuredDocument:
    law_name: str
    markdown: str  # Markdown with heading hierarchy preserved
    source_url: str


def parse_to_markdown(raw_document) -> StructuredDocument:
    """Convert a RawDocument into a StructuredDocument.

    TODO (Sprint 1):
      - Pick LlamaParse or Unstructured (see architecture doc Section 4.2
        for why either was chosen over flattening the doc to plain text)
      - Convert raw_document.raw_html (or PDF bytes) to Markdown
      - Verify Chapter/Section/Article/Clause headings map to Markdown
        heading levels correctly — this is the input the chunker relies on
    """
    raise NotImplementedError
