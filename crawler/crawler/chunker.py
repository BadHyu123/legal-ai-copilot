"""
Semantic chunking by Điều (Article) / Khoản (Clause), per architecture
doc Section 3.1. Never split on a fixed word count — always split on the
document's own semantic boundaries so each chunk is a complete,
self-contained legal unit.

Rule of thumb (Section 3.1): one chunk per Article, or one chunk per
Clause when a single Article is unusually long.

Reads the Markdown produced by parser.py (### Điều N. Title headings).
parser.py emits one line per source paragraph, so a Khoản boundary is a
line starting with its number + period ("2. Nhà nước..."). Numbers
mid-sentence (percentages, day counts) never start a line. Clauses
inserted by an amendment carry a letter ("1a.") and, in consolidated
texts (VBHN), often a footnote number glued after the period ("1a.21 Tổ
chức...", where 21 is the footnote).
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
# A single Khoản above this is split again by Điểm (a, b, c...). Decrees
# have Khoản of 20 points / 14k chars: three of those overflow the LLM's
# 8k-token context, and the reranker (512 tokens) only sees their start.
MAX_KHOAN_CHARS = 2 * MAX_CHUNK_CHARS

DIEU_MD_RE = re.compile(r"^### Điều\s+(\d{1,3})\.\s*(.*)$")
HEADING_RE = re.compile(r"^#{1,3}\s")
KHOAN_RE = re.compile(r"^(\d{1,2})([a-zđ]?)\.\d*\s+", re.MULTILINE)
DIEM_RE = re.compile(r"^([a-zđ])\)\s+", re.MULTILINE)
DIEM_ORDER = "abcdđeghiklmnopqrstuvxy"  # Vietnamese point letters, in order


class Chunk:
    def __init__(self, text: str, metadata: "ChunkMetadata"):
        self.text = text
        self.metadata = metadata


def _is_khoan_sequence(labels: list[tuple[str, str]]) -> bool:
    """Real Khoản run 1, 2, 3, ..., with amendment-inserted ones ("1a",
    "1b") right after their base number. Gaps are allowed: consolidated
    texts leave out repealed Khoản (1, 2, 4, 5). A number that doesn't go
    up means a numbered list inside a clause (e.g. quoted text in an
    amending Article) was mistaken for boundaries — and a repeated label
    would collide on the luat|dieu|khoan point ID, silently overwriting a
    clause.
    """
    prev = 0
    for num, letter in labels:
        n = int(num)
        if (n != prev) if letter else (n <= prev):
            return False
        prev = n
    return True


def _split_by_diem(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Same as _split_by_khoan, one level down: (lead-in, [(letter, text)]).
    Letters must run in order (gaps allowed, as for Khoản)."""
    matches = list(DIEM_RE.finditer(text))
    order = [DIEM_ORDER.find(m.group(1)) for m in matches]
    if len(matches) < 2 or any(b <= a for a, b in zip(order, order[1:])):
        return "", []
    segments = [(m.group(1), text[m.end():(matches[i + 1].start() if i + 1 < len(matches) else len(text))].strip())
                for i, m in enumerate(matches)]
    return text[:matches[0].start()].strip(), segments


def _split_by_khoan(body_text: str) -> tuple[str, list[tuple[str, str]]]:
    """Split an Article's body into (intro, [(khoan_label, khoan_text), ...]).
    `intro` is the lead-in before Khoản 1 ("Thu nhập chịu thuế gồm các
    loại sau đây:"), which every Khoản needs to be read correctly.
    Returns ("", []) when no reliable Khoản boundary is found (caller then
    keeps the Article as one chunk).
    """
    matches = list(KHOAN_RE.finditer(body_text))
    # A single match is usually just "1." with no real second clause to
    # split against — not worth fragmenting for.
    if len(matches) < 2 or not _is_khoan_sequence([m.groups() for m in matches]):
        return "", []

    segments = []
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body_text)
        segments.append((m.group(1) + m.group(2), body_text[m.end():end].strip()))
    return body_text[:matches[0].start()].strip(), segments


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

        intro, khoan_segments = _split_by_khoan(body_text)
        if not khoan_segments:
            logger.warning(
                "%s (%s) is %d chars, over the %d-char threshold, but no reliable "
                "Khoản boundary was found — keeping as one oversized chunk. "
                "Worth a manual look at this Article.",
                dieu_label, current_title, len(full_text), MAX_CHUNK_CHARS,
            )
            chunks.append(Chunk(full_text, ChunkMetadata(khoan=None, **base_metadata_kwargs)))
            return

        header = f"{dieu_label}. {current_title}" + (f"\n\n{intro}" if intro else "")
        for khoan_num, khoan_text in khoan_segments:
            khoan_label = f"Khoản {khoan_num}"
            text = f"{header}\n\n{khoan_label}. {khoan_text}"
            lead, diem_segments = _split_by_diem(khoan_text) if len(text) > MAX_KHOAN_CHARS else ("", [])
            if not diem_segments:
                chunks.append(Chunk(text, ChunkMetadata(khoan=khoan_label, **base_metadata_kwargs)))
                continue
            # "Khoản 3, điểm a" stays unique, so the luat|dieu|khoan key holds.
            for letter, diem_text in diem_segments:
                text = f"{header}\n\n{khoan_label}. {lead}\n\n{letter}) {diem_text}"
                chunks.append(Chunk(text, ChunkMetadata(khoan=f"{khoan_label}, điểm {letter}",
                                                        **base_metadata_kwargs)))

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
    from crawler.sources import luatvietnam
    from crawler.parser import parse_to_markdown

    _logging.basicConfig(level=_logging.INFO)
    docs = luatvietnam.list_documents(law_filter=("Lao động",))
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
        print("No documents fetched — check network / sources/luatvietnam.py first.")
