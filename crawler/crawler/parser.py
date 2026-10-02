"""
Parses raw crawled documents (the cleaned law-text HTML from
sources/luatvietnam.py) into structured Markdown that preserves heading hierarchy
(Chương -> Mục -> Điều), per architecture doc Section 3.3. Khoản-level
splitting is intentionally NOT done here — that's chunker.py's job per
Section 3.1 (split further only when an Article is unusually long).

KEY PARSING RULE (evidence-based, checked against a live document):
  A genuine "Điều N." heading always has the sentence-ending period
  immediately after the number ("Điều 1. Phạm vi điều chỉnh"). An inline
  cross-reference to another article never does ("...quy định tại Điều 29
  của Bộ luật này", "...theo quy định tại khoản 4 Điều 97 của Bộ luật
  này" — no period after the number). This is what DIEU_LINE_RE relies on
  to avoid misreading a cross-reference as a new heading. Chương/Mục
  headings use a looser rule — see _heading_match().

CAVEAT (only reason this could misfire): article/chapter titles are
assumed to contain no internal period, so the title is taken as the text
up to the first period after "Điều N. " / after the roman numeral. Every
title observed in the source document followed this, but if a future law
has a title containing a period, that title would get truncated — worth
a spot-check on the parsed output before trusting it at scale.
"""

import re
from dataclasses import dataclass

# Real-page variants seen live: "Chương I", "Chương I.", "Chương VI TIỀN
# LƯƠNG" (title on the same line), "Mục 1 GIAO KẾT..." (no period),
# "Điều 66 . Nguyên tắc..." (space before the period).
CHUONG_LINE_RE = re.compile(r"^Chương\s+(?P<num>[IVXLCDM]+)\b(?P<dot>\.?)\s*(?P<title>.*)$")
MUC_LINE_RE = re.compile(r"^Mục\s+(?P<num>\d+)\b(?P<dot>\.?)\s*(?P<title>.*)$")
DIEU_LINE_RE = re.compile(r"^Điều\s+(\d{1,3})\s*\.\s*(.*)$")
# A rule ("______", "-------") after the first Điều starts the signature /
# VBHN authentication / footnote block — never Article text. Matched
# anywhere in the line: that block is often a table, so the rule shares a
# collapsed row with "VĂN PHÒNG QUỐC HỘI" (checked on all live documents:
# no rule appears before the last Article).
SEPARATOR_LINE_RE = re.compile(r"[_\-–—=]{5,}")
# Consolidated texts (VBHN) glue a footnote number onto a clause number:
# "1.4 Lao động nữ..." is Khoản 1 + footnote 4, which reads like "khoản
# 1.4". Vietnamese writes decimals with a comma, so "N.M " opening a
# paragraph is never a number. (Thousands like "1.000" have 3 digits —
# excluded by the 1-2 digit footnote match.) Live pages also add a
# "[4]" link to the same footnote ("1.4[4] Lao động nữ..."); those
# bracketed markers are stripped everywhere — they only point at the
# footnote block, which is cut off below the Articles.
FOOTNOTE_AFTER_CLAUSE_RE = re.compile(r"^(\d{1,2}[a-zđ]?)\.\d{1,2}(?=\s)")
FOOTNOTE_LINK_RE = re.compile(r"\[\d{1,3}\]")

# Inline tags (<b>, <a> cross-references, <span>) must NOT break a line —
# only block-level boundaries do. get_text(separator="\n") breaks on every
# tag, which split "B<span>Ộ</span> LUẬT" and every sentence containing a
# linked cross-reference into fragments.
_BLOCK_TAGS = ["p", "div", "li", "tr", "td", "th", "table", "br",
               "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"]


def _heading_match(regex: re.Pattern, line: str) -> re.Match | None:
    """Chương/Mục headings either have a period after the number ("Mục 1.
    Giao kết...", same evidence rule as Điều) or an UPPERCASE same-line
    title ("Mục 1 GIAO KẾT...") or no title at all. Anything else — e.g.
    "Mục 2 của Chương này..." starting a body line — is a cross-reference.
    """
    m = regex.match(line)
    if m and (m["dot"] or not m["title"] or m["title"].isupper()):
        return m
    return None


def _is_heading(line: str) -> bool:
    return bool(_heading_match(CHUONG_LINE_RE, line)
                or _heading_match(MUC_LINE_RE, line)
                or DIEU_LINE_RE.match(line))


@dataclass
class StructuredDocument:
    law_name: str
    markdown: str  # Markdown with heading hierarchy preserved
    source_url: str


def _extract_lines(raw_html: str) -> list[str]:
    """HTML -> a flat list of non-empty text lines, one per block element
    (see _BLOCK_TAGS). Whitespace inside a line is collapsed (incl. &nbsp;).
    """
    from bs4 import BeautifulSoup  # local import: parser.py only needs bs4 at call time

    soup = BeautifulSoup(raw_html, "lxml")
    # One line per table row, cells joined by " | " — tax brackets and rate
    # tables are otherwise flattened to one cell per line, which neither the
    # LLM nor a reader can map back to rows. Innermost rows first, so a
    # nested table's text is collapsed before its parent row reads it.
    for tr in reversed(soup.find_all("tr")):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"], recursive=False)]
        tr.clear()
        tr.append(" | ".join(c for c in cells if c))
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    lines = (" ".join(FOOTNOTE_LINK_RE.sub("", line).split()) for line in soup.get_text().split("\n"))
    return [line for line in lines if line]


def _title_from_next_line(lines: list[str], i: int) -> str:
    """A Chương/Mục title is conventionally the next line, unless that line
    is itself a heading (title omitted)."""
    if i + 1 < len(lines) and not _is_heading(lines[i + 1]):
        return lines[i + 1]
    return ""


def parse_to_markdown(raw_document) -> StructuredDocument:
    lines = _extract_lines(raw_document.raw_html)

    md: list[str] = [f"# {raw_document.law_name}", ""]
    i = 0
    n = len(lines)
    seen_dieu = False

    while i < n:
        line = lines[i]

        if seen_dieu and SEPARATOR_LINE_RE.search(line):
            break

        chuong_match = _heading_match(CHUONG_LINE_RE, line)
        muc_match = None if chuong_match else _heading_match(MUC_LINE_RE, line)
        heading_match = chuong_match or muc_match
        if heading_match:
            title = heading_match["title"]
            if not title:
                title = _title_from_next_line(lines, i)
                if title:
                    i += 1
            prefix = "# Chương" if chuong_match else "## Mục"
            md.append(f"{prefix} {heading_match['num']}" + (f". {title}" if title else ""))
            md.append("")
            i += 1
            continue

        dieu_match = DIEU_LINE_RE.match(line)
        if dieu_match:
            seen_dieu = True
            num = dieu_match.group(1)
            rest = dieu_match.group(2)
            # Title = text up to the first period (see module docstring
            # caveat). Anything after that period is body text that was
            # on the same line/block as the heading — keep it, don't drop it.
            title, sep, body_rest = rest.partition(".")
            md.append(f"### Điều {num}. {title.strip()}")
            md.append("")
            if sep and body_rest.strip():
                md.append(body_rest.strip())
            i += 1
            continue

        # Plain body line — belongs to whatever heading (or front matter,
        # if before the first Chương/Điều) came before it.
        md.append(FOOTNOTE_AFTER_CLAUSE_RE.sub(r"\1.", line))
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
    from crawler.sources import luatvietnam

    logging.basicConfig(level=logging.INFO)
    docs = luatvietnam.list_documents(law_filter=("Lao động",))
    if docs:
        structured = parse_to_markdown(docs[0])
        print(structured.markdown[:3000])
        print(f"\n... ({len(structured.markdown)} chars total)")
    else:
        print("No documents fetched — check network / sources/luatvietnam.py first.")
