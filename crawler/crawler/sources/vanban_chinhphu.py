"""
Source adapter for vanban.chinhphu.vn (architecture doc, Section 3.4).

Authoritative source for confirming a document is currently in effect.
Used alongside thuvienphapluat.vn, not as the primary parsing source.
"""

from crawler.sources.thuvienphapluat import RawDocument


def list_documents(law_filter: tuple[str, ...] = ("Labor Law", "Tax Law")) -> list[RawDocument]:
    """Fetch documents from the government portal for effective-status cross-check.

    TODO (Sprint 1):
      - Fetch listing/index pages for Labor Law and Tax Law
      - Return RawDocument objects; effective-status confirmation logic
        can live here or in parser.py depending on what the site exposes
    """
    raise NotImplementedError
