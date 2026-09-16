"""
Parses raw crawled documents (HTML from thuvienphapluat.vn's #tab1
content div) into structured Markdown that preserves heading hierarchy
(Chương -> Mục -> Điều), per architecture doc Section 3.3. Khoản-level
splitting is intentionally NOT done here — that's chunker.py's job per
Section 3.1 (split further only when an Article is unusually long).

KEY PARSING RULE (evidence-based, checked against a live document):
  A genuine "Điều N." heading always has the sentence-ending period
  immediately after the number ("Điều 1. Phạm vi điều chỉnh"). An inline
  cross-reference to another article never does ("...quy định tại Điều 29
  của Bộ luật này", "...theo quy định tại khoản 4 Điều 97 của Bộ luật
  này" — no period after the number). The same holds for "Chương" +
  roman numeral. This is what DIEU_LINE_RE and CHUONG_LINE_RE rely on to
  avoid misreading a cross-reference as a new heading.

CAVEAT (only reason this could misfire): article/chapter titles are
assumed to contain no internal period, so the title is taken as the text
up to the first period after "Điều N. " / after the roman numeral. Every
title observed in the source document followed this, but if a future law
has a title containing a period, that title would get truncated — worth
a spot-check on the parsed output before trusting it at scale.
"""

import re
from dataclasses import dataclass

CHUONG_LINE_RE = re.compile(r"^Chương\s+([IVXLCDM]+)\s*$")
MUC_LINE_RE = re.compile(r"^Mục\s+(\d+)\.\s*(.+)$")
DIEU_LINE_RE = re.compile(r"^Điều\s+(\d{1,3})\.\s*(.*)$")


@dataclass
class StructuredDocument:
    law_name: str
    markdown: str  # Markdown with heading hierarchy preserved
    source_url: str


def _extract_lines(raw_html: str) -> list[str]:
    """HTML -> a flat list of non-empty text lines.

    BeautifulSoup's get_text(separator="\\n") inserts a newline between
    sibling tags, which is what separates a heading from the paragraph
    that follows it in the source markup (each is its own <p> / <strong>
    run). This is a structural assumption, not a guess about specific
    CSS classes, so it should hold even if the site's styling changes.
    """
    from bs4 import BeautifulSoup  # local import: parser.py only needs bs4 at call time

    soup = BeautifulSoup(raw_html, "lxml")
    text = soup.get_text(separator="\n")
    return [line.strip() for line in text.split("\n") if line.strip()]


def parse_to_markdown(raw_document) -> StructuredDocument:
    lines = _extract_lines(raw_document.raw_html)

    md: list[str] = [f"# {raw_document.law_name}", ""]
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        chuong_match = CHUONG_LINE_RE.match(line)
        if chuong_match:
            roman = chuong_match.group(1)
            title = ""
            # The chapter title is conventionally the next line, unless
            # that line is itself another heading (title omitted / two
            # headings back-to-back, which shouldn't normally happen but
            # is handled defensively).
            if i + 1 < n and not (
                CHUONG_LINE_RE.match(lines[i + 1])
                or MUC_LINE_RE.match(lines[i + 1])
                or DIEU_LINE_RE.match(lines[i + 1])
            ):
                title = lines[i + 1]
                i += 1
            heading = f"# Chương {roman}" + (f". {title}" if title else "")
            md.append(heading)
            md.append("")
            i += 1
            continue

        muc_match = MUC_LINE_RE.match(line)
        if muc_match:
            md.append(f"## Mục {muc_match.group(1)}. {muc_match.group(2)}")
            md.append("")
            i += 1
            continue

        dieu_match = DIEU_LINE_RE.match(line)
        if dieu_match:
            num = dieu_match.group(1)
            rest = dieu_match.group(2)
            # Title = text up to the first period (see module docstring
            # caveat). Anything after that period is body text that was
            # on the same line/block as the heading — keep it, don't drop it.
            title, sep, body_rest = rest.partition(".")
            md.append(f"### Điều {num}. {title.strip()}")
            md.append("")
            if sep and body_rest.strip():
                md.append(body_rest.strip() + ".")
            i += 1
            continue

        # Plain body line — belongs to whatever heading (or front matter,
        # if before the first Chương/Điều) came before it.
        md.append(line)
        i += 1

    return StructuredDocument(
        law_name=raw_document.law_name,
        markdown="\n".join(md).strip() + "\n",
        source_url=raw_document.url,
    )


if __name__ == "__main__":
    # Manual smoke test against a live document:
    # python -m crawler.parser
    import logging
    from crawler.sources import thuvienphapluat

    logging.basicConfig(level=logging.INFO)
    docs = thuvienphapluat.list_documents(law_filter=("Bộ luật Lao động",))
    if docs:
        structured = parse_to_markdown(docs[0])
        print(structured.markdown[:3000])
        print(f"\n... ({len(structured.markdown)} chars total)")
    else:
        print("No documents fetched — check network / thuvienphapluat.py first.")
