"""
Source adapter for thuvienphapluat.vn (architecture doc, Section 3.4).

Primary source: more consistently structured for parsing than
vanban.chinhphu.vn, so it's the main text source. vanban.chinhphu.vn is
used to cross-check that a document is still in effect (see
vanban_chinhphu.py).
"""

from dataclasses import dataclass


@dataclass
class RawDocument:
    url: str
    title: str
    law_name: str
    raw_html: str


def list_documents(law_filter: tuple[str, ...] = ("Labor Law", "Tax Law")) -> list[RawDocument]:
    """Fetch the listing pages for the given laws and return raw documents.

    TODO (Sprint 1):
      - Fetch listing/index pages for Labor Law and Tax Law
      - For each entry, fetch the full document page
      - Return RawDocument objects (do not parse structure here — that's parser.py)
    """
    raise NotImplementedError
