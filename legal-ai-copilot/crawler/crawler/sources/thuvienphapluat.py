"""
Source adapter for thuvienphapluat.vn (architecture doc, Section 3.4).

Primary source: more consistently structured for parsing than
vanban.chinhphu.vn, so it's the main text source. vanban.chinhphu.vn is
used to cross-check that a document is still in effect (see
vanban_chinhphu.py).

DOM notes verified against a live document page before writing this
(https://thuvienphapluat.vn/van-ban/Lao-dong-Tien-luong/Bo-Luat-lao-dong-2019-333670.aspx):
  - Document pages are tabbed; the tab navigation links to #tab1 for
    "Nội dung" (full text), so the content lives in an element with
    id="tab1". This is read off the site's own anchor scheme rather
    than guessed, so it's the one selector this module leans on hard.
  - A "Thuộc tính" attributes table exposes label/value pairs including
    "Tình trạng" (effective status, e.g. "Còn hiệu lực") — used to skip
    ingesting laws that are no longer in force.
  - Search results are served from /page/tim-van-ban.aspx?keyword=...

CAVEAT: thuvienphapluat.vn's exact table markup wasn't inspected at the
raw-HTML level (only via a markdown-extracted fetch), so
_parse_attributes()'s cell-pairing logic is a defensive best-effort —
verify against real HTML on first run and adjust if attributes come back
empty (see the TODO in that function).
"""

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://thuvienphapluat.vn"
SEARCH_URL = f"{BASE_URL}/page/tim-van-ban.aspx"

# Vietnamese search keywords -> internal law_name used throughout the
# pipeline (chunk metadata, backend filters, etc.). Extend this as more
# laws are added beyond the Sprint 1 scope (Labor Law, Tax Law).
LAW_SEARCH_KEYWORDS: dict[str, str] = {
    "Bộ luật Lao động": "Bộ luật Lao động 2019",
    "Luật Thuế thu nhập cá nhân": "Luật Thuế thu nhập cá nhân",
    "Luật Thuế thu nhập doanh nghiệp": "Luật Thuế thu nhập doanh nghiệp",
    "Luật Quản lý thuế": "Luật Quản lý thuế",
}

HEADERS = {
    # A real UA avoids some basic bot-blocking; polite/identifiable is
    # still preferable to spoofing a browser 1:1.
    "User-Agent": "Mozilla/5.0 (compatible; LegalAICopilotBot/0.1; "
                  "+https://github.com/your-org/legal-ai-copilot)"
}


@dataclass
class RawDocument:
    url: str
    title: str
    law_name: str
    raw_html: str
    effective_status: str = "unknown"   # e.g. "Còn hiệu lực" / "Hết hiệu lực"
    attributes: dict = field(default_factory=dict)  # full Thuộc tính table, for traceability


def _fetch(url: str) -> str:
    resp = httpx.get(url, headers=HEADERS, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _search_document_urls(keyword: str, max_results: int = 5) -> list[str]:
    """Search thuvienphapluat.vn for a keyword and return document page URLs.

    TODO (Sprint 1, verify on first live run): result-link selectors are
    inferred from the site's URL convention (/van-ban/.../*.aspx) rather
    than a specific CSS class, since that's what's reliably stable across
    site redesigns. If results come back empty, inspect the live search
    page HTML and tighten this to the actual result-list container.
    """
    html = _fetch(f"{SEARCH_URL}?keyword={keyword}&match=True&area=0")
    soup = BeautifulSoup(html, "lxml")

    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/van-ban/" in href and href.endswith(".aspx"):
            full_url = urljoin(BASE_URL, href)
            if full_url not in urls:
                urls.append(full_url)
        if len(urls) >= max_results:
            break
    return urls


def _parse_attributes(soup: BeautifulSoup) -> dict:
    """Parse the 'Thuộc tính' label/value table into a dict.

    Best-effort generic table-cell pairing (label cell followed by value
    cell), since the exact table class wasn't confirmed against raw HTML.
    """
    attrs: dict = {}
    known_labels = {
        "Số hiệu", "Loại văn bản", "Nơi ban hành", "Người ký",
        "Ngày ban hành", "Ngày hiệu lực", "Ngày công báo", "Số công báo",
        "Tình trạng",
    }
    for row in soup.find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        # Rows can hold two label:value pairs side by side (as seen on
        # the live page: "Số hiệu | ... | Loại văn bản | ...").
        i = 0
        while i < len(cells) - 1:
            label = cells[i].rstrip(":")
            if label in known_labels:
                attrs[label] = cells[i + 1]
                i += 2
            else:
                i += 1
    return attrs


def _parse_content(soup: BeautifulSoup) -> str:
    """Extract the full-text content div (id="tab1") as HTML.

    Falls back to the whole page body if #tab1 isn't found, so the
    caller still gets *something* to inspect rather than an empty string
    — parser.py should treat an unexpectedly short/unstructured result
    as a signal this selector needs updating.
    """
    content = soup.find(id="tab1")
    if content is None:
        logger.warning("Could not find #tab1 content div — falling back to <body>. "
                        "Selector likely needs updating against live HTML.")
        content = soup.find("body")
    return str(content) if content else ""


def fetch_document(url: str) -> RawDocument:
    html = _fetch(url)
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    attributes = _parse_attributes(soup)
    content_html = _parse_content(soup)

    return RawDocument(
        url=url,
        title=title,
        law_name=title,  # refined by the caller in list_documents() against LAW_SEARCH_KEYWORDS
        raw_html=content_html,
        effective_status=attributes.get("Tình trạng", "unknown"),
        attributes=attributes,
    )


def list_documents(law_filter: tuple[str, ...] = tuple(LAW_SEARCH_KEYWORDS)) -> list[RawDocument]:
    """Search for and fetch each target law, returning only documents
    that are currently in effect.

    `law_filter` entries must be keys of LAW_SEARCH_KEYWORDS.
    """
    documents: list[RawDocument] = []

    for keyword in law_filter:
        law_name = LAW_SEARCH_KEYWORDS.get(keyword, keyword)
        try:
            urls = _search_document_urls(keyword)
        except httpx.HTTPError as e:
            logger.error("Search failed for %r: %s", keyword, e)
            continue

        if not urls:
            logger.warning("No search results for %r — check _search_document_urls().", keyword)
            continue

        # Take the first result: thuvienphapluat.vn ranks the canonical/
        # most-current version of a law first for an exact-name search.
        url = urls[0]
        try:
            doc = fetch_document(url)
        except httpx.HTTPError as e:
            logger.error("Failed to fetch %s: %s", url, e)
            continue

        doc.law_name = law_name

        if doc.effective_status and doc.effective_status != "unknown" \
                and "hiệu lực" in doc.effective_status.lower() \
                and "hết" in doc.effective_status.lower():
            logger.info("Skipping %s — no longer in effect (%s)", law_name, doc.effective_status)
            continue

        documents.append(doc)

    return documents


if __name__ == "__main__":
    # Manual smoke test: python -m crawler.sources.thuvienphapluat
    logging.basicConfig(level=logging.INFO)
    docs = list_documents(law_filter=("Bộ luật Lao động",))
    for d in docs:
        print(f"{d.law_name} | {d.url} | status={d.effective_status} | "
              f"content_len={len(d.raw_html)}")
