"""
Shared chunk metadata contract.

Every chunk written to the Vector DB by the crawler (Sprint 1) must carry
this metadata, and every chunk read back by the backend (Sprint 2) can
rely on it being present. This is what makes citations traceable end to
end (architecture doc, Section 3.2 / 3.14) without either side having to
guess the other's shape.

Keep this file dependency-free (stdlib only) so it can be imported by
both the crawler container and the backend container without pulling in
unrelated packages.
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ChunkMetadata:
    """Metadata attached to a single embedded chunk.

    Field names intentionally match the architecture doc's example
    (Section 3.2) so ingestion output and retrieval code line up 1:1
    with the design doc.
    """

    luat: str            # "luật" — e.g. "Luật Lao động 2019"
    dieu: str             # "điều" — e.g. "Điều 36"
    chu_de: str           # "chủ_đề" — short topic/summary of the article
    khoan: Optional[str] = None   # "khoản" — set when chunked at clause level (long articles)
    source_url: Optional[str] = None   # crawl source page this was parsed from
    document_hash: Optional[str] = None  # for change-detection traceability

    def to_dict(self) -> dict:
        return asdict(self)


# TODO (Sprint 1): decide final Vietnamese vs. ASCII key names once the
# Vector DB client library's filtering syntax is confirmed (Qdrant supports
# unicode field names, but double-check ChromaDB if that's the final choice —
# see architecture doc Section 3.8).
