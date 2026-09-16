"""
Semantic chunking by Điều (Article) / Khoản (Clause), per architecture
doc Section 3.1. Never split on a fixed word count — always split on the
document's own semantic boundaries so each chunk is a complete,
self-contained legal unit.

Rule of thumb (Section 3.1): one chunk per Article, or one chunk per
Clause when a single Article is unusually long.

Reads the Markdown produced by parser.py (### Điều N. Title headings).
Khoản-level splitting relies on the same evidence-based rule used in
parser.py for Điều: a real Khoản boundary is a number+period that starts
right after the previous clause's sentence-ending period (or at the very
start of the Article body) — e.g. "...không cấm.2. Nhà nước..." — which
avoids false positives on numbers appearing mid-sentence (percentages,
day counts, etc. are never immediately preceded by a period).
"""

import logging
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "shared"))
from metadata_schema import ChunkMetadata  # noqa: E402

logger = logging.getLogger(__name__)

# Above this many characters, an Article is split by Khoản instead of
# kept as one chunk. ~1500 chars is roughly 350-450 tokens for Vietnamese
# legal text — comfortably inside typical embedding model context while
# still being a meaningfully-sized retrieval unit.
MAX_CHUNK_CHARS = 1500

DIEU_MD_RE = re.compile(r"^### Điều\s+(\d{1,3})\.\s*(.*)$")
HEADING_RE = re.compile(r"^#{1,3}\s")
KHOAN_RE = re.compile(r"(?:^|(?<=\.))\s*(\d{1,2})\.\s+")


class Chunk:
    def __init__(self, text: str, metadata: "ChunkMetadata"):
        self.text = text
        self.metadata = metadata


def _split_by_khoan(body_text: str) -> list[tuple[str, str]]:
    """Split an Article's body into (khoan_number, khoan_text) pairs.
    Returns [] if no reliable Khoản boundary is found (caller should then
    fall back to keeping the Article as one chunk).
    """
    matches = list(KHOAN_RE.finditer(body_text))
    if len(matches) < 2:
        # A single match is usually just "1." with no real second clause
        # to split against — not worth fragmenting for.
        return []

    segments = []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body_text)
        khoan_num = m.group(1)
        khoan_text = body_text[start:end].strip()
        if khoan_text:
            segments.append((khoan_num, khoan_text))
    return segments


def chunk_by_article(structured_document) -> list[Chunk]:
    lines = structured_document.markdown.split("\n")

    chunks: list[Chunk] = []
    current_num: str | None = None
    current_title: str = ""
    current_body_lines: list[str] = []

    def flush() -> None:
        if current_num is None:
            return
        body_text = "\n".join(l for l in current_body_lines if l.strip()).strip()
        dieu_label = f"Điều {current_num}"
        full_text = f"{dieu_label}. {current_title}\n\n{body_text}".strip()

        base_metadata_kwargs = dict(
            luat=structured_document.law_name,
            dieu=dieu_label,
            chu_de=current_title,
            source_url=structured_document.source_url,
        )

        if len(full_text) <= MAX_CHUNK_CHARS:
            chunks.append(Chunk(full_text, ChunkMetadata(khoan=None, **base_metadata_kwargs)))
            return

        khoan_segments = _split_by_khoan(body_text)
        if not khoan_segments:
            logger.warning(
                "%s (%s) is %d chars, over the %d-char threshold, but no reliable "
                "Khoản boundary was found — keeping as one oversized chunk. "
                "Worth a manual look at this Article.",
                dieu_label, current_title, len(full_text), MAX_CHUNK_CHARS,
            )
            chunks.append(Chunk(full_text, ChunkMetadata(khoan=None, **base_metadata_kwargs)))
            return

        for khoan_num, khoan_text in khoan_segments:
            khoan_label = f"Khoản {khoan_num}"
            text = f"{dieu_label}. {current_title}\n\n{khoan_label}. {khoan_text}"
            chunks.append(Chunk(text, ChunkMetadata(khoan=khoan_label, **base_metadata_kwargs)))

    for line in lines:
        stripped = line.strip()
        dieu_match = DIEU_MD_RE.match(stripped)

        if dieu_match:
            flush()
            current_num = dieu_match.group(1)
            current_title = dieu_match.group(2).strip()
            current_body_lines = []
        elif HEADING_RE.match(stripped):
            # Chương / Mục heading, or the document's top "# {law_name}"
            # line — none of these carry Article body content.
            flush()
            current_num = None
            current_title = ""
            current_body_lines = []
        elif current_num is not None:
            current_body_lines.append(line)
        # else: front-matter text before the first Điều — intentionally
        # dropped, since it's preamble ("Quốc hội ban hành...") rather
        # than a citable legal unit.

    flush()
    return chunks


if __name__ == "__main__":
    # Manual smoke test against a live document:
    # python -m crawler.chunker
    import logging as _logging
    from crawler.sources import thuvienphapluat
    from crawler.parser import parse_to_markdown

    _logging.basicConfig(level=_logging.INFO)
    docs = thuvienphapluat.list_documents(law_filter=("Bộ luật Lao động",))
    if docs:
        structured = parse_to_markdown(docs[0])
        chunks = chunk_by_article(structured)
        print(f"{len(chunks)} chunks produced\n")
        for c in chunks[:3]:
            print(f"--- {c.metadata.dieu} (khoan={c.metadata.khoan}) "
                  f"[{len(c.text)} chars] ---")
            print(c.text[:300])
            print()
    else:
        print("No documents fetched — check network / thuvienphapluat.py first.")
