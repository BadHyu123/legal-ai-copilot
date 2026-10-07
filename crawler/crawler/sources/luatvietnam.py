"""
Source adapter for luatvietnam.vn — the primary full-text source
(architecture doc, Section 3.4).

Why not thuvienphapluat.vn (the original design): checked live on
2026-10-02, every page there sits behind a Cloudflare managed challenge
("Just a moment... Enable JavaScript and cookies") for any non-browser
client. That is a deliberate bot block, so this project does not try to
get around it. vanban.chinhphu.vn only offers scanned PDFs (no text
layer), and vbpl.vn disallows /api/ in robots.txt. luatvietnam.vn serves
the full text as HTML and its robots.txt allows document pages (only
search URLs are disallowed — this module never uses search).

Fixed document list instead of keyword search: luatvietnam.vn's
"Tình trạng hiệu lực" field is paywalled ("Đã biết — Tiện ích dành cho
tài khoản Tiêu chuẩn hoặc Nâng cao"), so effective status can't be read
off the page. The list below is curated by hand to the in-force version
of each law instead — preferring the National Assembly Office's
consolidated texts (văn bản hợp nhất, VBHN), which are the official basis
for applying the law from 01/07/2026. Re-check this list when a law is
amended; that curation IS the effective-status check now.

DOM notes (verified against live pages):
  - Law text: the `.the-document-body` inside `#noidung` (the "Nội dung"
    tab). Each paragraph is a `div.docitem-N`.
  - Noise inside it, removed before parsing: `.tooltip-button` (a
    "Đang theo dõi" UI label after every paragraph) and
    `.docitem-binhluan` (LuatVietnam's editorial notes about later
    amendments — not law text, so never cite them).
"""

import logging
import re
import time
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://luatvietnam.vn"

# (law_name used in chunk metadata + citations, Số hiệu of the underlying
# law for the vanban.chinhphu.vn cross-check, document page path)
DOCUMENTS: list[tuple[str, str, str]] = [
    ("Bộ luật Lao động 2019 (hợp nhất 2026)", "45/2019/QH14",
     "/lao-dong/van-ban-hop-nhat-18-vbhn-vpqh-2026-hop-nhat-bo-luat-lao-dong-426612-d5.html"),
    # Contract review checks salaries against it; without it the LLM
    # flagged a 12-million salary as "not shown to meet the minimum".
    ("Nghị định 293/2025/NĐ-CP về mức lương tối thiểu", "293/2025/NĐ-CP",
     "/lao-dong/nghi-dinh-293-2025-nd-cp-quy-dinh-muc-luong-toi-thieu-cho-nguoi-lao-dong-hop-dong-418212-d1.html"),
    ("Luật Thuế thu nhập cá nhân 2025 (hợp nhất 2026)", "109/2025/QH15",
     "/thue/van-ban-hop-nhat-112-vbhn-vpqh-2026-luat-thue-thu-nhap-ca-nhan-435386-d5.html"),
    ("Luật Thuế thu nhập doanh nghiệp 2025 (hợp nhất 2026)", "67/2025/QH15",
     "/thue/van-ban-hop-nhat-113-vbhn-vpqh-2026-luat-thue-thu-nhap-doanh-nghiep-435747-d5.html"),
    # ponytail: VBHN 12 predates the 09/2026/QH16 amendments to the VAT
    # law; swap in the newer VBHN once the National Assembly Office issues it.
    ("Luật Thuế giá trị gia tăng 2024 (hợp nhất 2026)", "48/2024/QH15",
     "/thue/van-ban-hop-nhat-12-vbhn-vpqh-2026-luat-thue-gia-tri-gia-tang-426350-d5.html"),
    ("Luật Quản lý thuế 2025", "108/2025/QH15",
     "/thue/luat-quan-ly-thue-2025-so-108-2025-qh15-421539-d1.html"),
    # Guiding decrees: practical tax questions (allowances, deductions,
    # invoices, household businesses, penalties) are answered there, not in
    # the laws. Consolidated (VBHN-BTC) where a decree was amended.
    # ponytail: circulars (Thông tư) not ingested; add when eval shows misses.
    ("Nghị định 253/2026/NĐ-CP hướng dẫn Luật Thuế thu nhập cá nhân", "253/2026/NĐ-CP",
     "/thue/nghi-dinh-253-2026-nd-cp-huong-dan-thi-hanh-luat-thue-thu-nhap-ca-nhan-chi-tiet-439303-d1.html"),
    ("Nghị định 320/2025/NĐ-CP hướng dẫn Luật Thuế thu nhập doanh nghiệp (hợp nhất 2026)", "320/2025/NĐ-CP",
     "/thue/van-ban-hop-nhat-19-vbhn-btc-2026-quy-dinh-chi-tiet-thi-hanh-luat-thue-thu-nhap-doanh-nghiep-436630-d5.html"),
    ("Nghị định 181/2025/NĐ-CP hướng dẫn Luật Thuế giá trị gia tăng (hợp nhất 2026)", "181/2025/NĐ-CP",
     "/thue/van-ban-hop-nhat-18-vbhn-btc-2026-quy-dinh-chi-tiet-thi-hanh-luat-thue-gia-tri-gia-tang-436641-d5.html"),
    ("Nghị định 252/2026/NĐ-CP hướng dẫn Luật Quản lý thuế", "252/2026/NĐ-CP",
     "/thue/nghi-dinh-252-2026-nd-cp-huong-dan-thi-hanh-luat-quan-ly-thue-chi-tiet-va-hieu-qua-439382-d1.html"),
    ("Nghị định 254/2026/NĐ-CP về hóa đơn điện tử", "254/2026/NĐ-CP",
     "/thue/nghi-dinh-254-2026-nd-cp-huong-dan-thi-hanh-luat-quan-ly-thue-2025-ve-hoa-don-dien-tu-439381-d1.html"),
    ("Nghị định 68/2026/NĐ-CP về thuế hộ kinh doanh, cá nhân kinh doanh (hợp nhất 2026)", "68/2026/NĐ-CP",
     "/thue/van-ban-hop-nhat-25-2026-vbhn-nd-btc-2026-quy-dinh-chinh-sach-thue-va-quan-ly-thue-cho-ho-kinh-doanh-444326-d5.html"),
    ("Nghị định 125/2020/NĐ-CP xử phạt vi phạm hành chính về thuế, hóa đơn (hợp nhất 2026)", "125/2020/NĐ-CP",
     "/thue/van-ban-hop-nhat-27-2026-vbhn-nd-btc-2026-xu-phat-vi-pham-hanh-chinh-ve-thue-va-hoa-don-445970-d5.html"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LegalAICopilotBot/0.1; "
                  "+https://github.com/your-org/legal-ai-copilot)"
}
REQUEST_DELAY_SECONDS = 2.0  # a handful of pages per weekly run — stay polite


@dataclass
class RawDocument:
    url: str
    title: str
    law_name: str
    so_hieu: str
    raw_html: str  # just the cleaned law-text element, as HTML


def _fetch(url: str) -> str:
    resp = httpx.get(url, headers=HEADERS, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def extract_law_html(page_html: str) -> str:
    """Pull the law-text element out of a document page and strip the
    site's UI/editorial noise. Returns "" when the layout isn't recognized,
    so a site redesign shows up as an empty document, not as garbage text.
    """
    soup = BeautifulSoup(page_html, "lxml")
    bodies = soup.select("#noidung .the-document-body")
    if not bodies:
        return ""
    body = max(bodies, key=lambda b: len(b.get_text()))
    for noise in body.select(".tooltip-button, .docitem-binhluan, script, style"):
        noise.decompose()
    # Consolidated texts (VBHN) mark amendment footnotes with <sup>N</sup>:
    # "từ 01 tỷ đồng<sup>2</sup>" read as "01 tỷ đồng2", "Điều 10.<sup>28</sup>
    # Xử phạt" as a title starting "28". A digit-only superscript is a
    # footnote unless it's a unit exponent (m², km³). Ministry of Finance
    # consolidations (VBHN-BTC) also put each note right after its paragraph
    # (<p id="footnote-N">), quoting the superseded figure ("500 triệu
    # đồng") — dropped too.
    for sup in body.select("sup"):
        mark = sup.get_text(strip=True)
        before = sup.find_previous(string=True) or ""
        if mark.isdigit() and not (mark in ("2", "3") and _UNIT_BEFORE_RE.search(before)):
            sup.decompose()
    for note in body.select('[id^="footnote-"]'):
        note.decompose()
    return str(body)


_UNIT_BEFORE_RE = re.compile(r"(?:^|[\s\d])[kcdm]?m\s*$")


def fetch_document(law_name: str, so_hieu: str, path: str) -> RawDocument:
    url = BASE_URL + path
    page_html = _fetch(url)
    soup = BeautifulSoup(page_html, "lxml")
    h1 = soup.find("h1")
    return RawDocument(
        url=url,
        title=h1.get_text(strip=True) if h1 else law_name,
        law_name=law_name,
        so_hieu=so_hieu,
        raw_html=extract_law_html(page_html),
    )


def list_documents(law_filter: tuple[str, ...] = ()) -> list[RawDocument]:
    """Fetch every document in DOCUMENTS (or only those whose law_name
    contains one of `law_filter`). A failed or unrecognized page is logged
    and skipped, so one bad page doesn't sink the whole weekly run.
    """
    documents: list[RawDocument] = []
    for law_name, so_hieu, path in DOCUMENTS:
        if law_filter and not any(f in law_name for f in law_filter):
            continue
        if documents:
            time.sleep(REQUEST_DELAY_SECONDS)
        try:
            doc = fetch_document(law_name, so_hieu, path)
        except httpx.HTTPError as e:
            logger.error("Failed to fetch %s: %s", law_name, e)
            continue
        if not doc.raw_html:
            logger.error("No law text found on %s — page layout changed? Check "
                         "extract_law_html() selectors against the live page.", doc.url)
            continue
        documents.append(doc)
    return documents


if __name__ == "__main__":
    # Manual smoke test: python -m crawler.sources.luatvietnam
    logging.basicConfig(level=logging.INFO)
    for d in list_documents(law_filter=("Lao động",)):
        print(f"{d.law_name} | {d.so_hieu} | {d.url} | content_len={len(d.raw_html)}")
