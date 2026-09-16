"""
Source adapter for vanban.chinhphu.vn (architecture doc, Section 3.4).

Cross-check source: confirms a law found on thuvienphapluat.vn genuinely
exists in the Government's own official document registry, and exposes
its "Ngày có hiệu lực" (effective date) for comparison.

IMPORTANT — verified against live pages before writing this, and this
changes what "cross-check effective status" can mean in practice:

  Unlike thuvienphapluat.vn, a Luật (law) detail page on vanban.chinhphu.vn
  (e.g. https://vanban.chinhphu.vn/?pageid=27160&docid=216541, Luật Quản
  lý thuế 108/2025/QH15) has NO explicit "Tình trạng" (còn/hết hiệu lực)
  field. Its attribute table only exposes: Số ký hiệu, Ngày ban hành,
  Ngày có hiệu lực, Loại văn bản, Cơ quan ban hành, Người ký, Trích yếu.

  So this source cannot directly answer "is this repealed?" — it can only
  confirm (a) the document is authentically registered with the
  Government and (b) whether its "Ngày có hiệu lực" has already passed.
  Treat thuvienphapluat.vn's "Tình trạng" field as the primary signal for
  repeal status; use this module as corroboration, not as the sole source
  of truth. This is a real constraint of the site, not a shortcut taken
  here — update this comment if a future redesign of the site adds a
  status field.

DOM notes verified against live pages:
  - The listing for "Luật - Pháp lệnh" is a plain GET:
    https://vanban.chinhphu.vn/he-thong-van-ban?classid=1&mode=1&typegroupid=3
    CAVEAT: combining typegroupid with orggroupid in the same query string
    was tried and did NOT work as expected (the site silently redirected
    to an unrelated category). Only the single confirmed param combination
    above is used here — do not add orggroupid without re-verifying live.
  - Document detail pages: https://vanban.chinhphu.vn/?pageid=27160&docid={id}
  - Pagination beyond page 1 is ASP.NET WebForms postback
    (__doPostBack('ctrl_191017_163$grvDocument','Page$N')), not a plain
    GET parameter. _postback() replays every current form field on the
    page with an updated __EVENTTARGET/__EVENTARGUMENT, which is the
    standard generic technique for this — but the exact control ID
    (ctrl_191017_163) was only observed on one page and may differ /
    change over time; verify against a live fetch if pagination breaks.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://vanban.chinhphu.vn"
LAW_LIST_URL = f"{BASE_URL}/he-thong-van-ban?classid=1&mode=1&typegroupid=3"
GRID_CONTROL_ID = "ctrl_191017_163$grvDocument"  # TODO: reconfirm live if pagination stops working

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LegalAICopilotBot/0.1; "
                  "+https://github.com/your-org/legal-ai-copilot)"
}


@dataclass
class EffectiveStatusResult:
    so_hieu: str
    found: bool
    url: Optional[str] = None
    ngay_ban_hanh: Optional[str] = None      # "Ngày ban hành", format dd-mm-yyyy
    ngay_hieu_luc: Optional[str] = None      # "Ngày có hiệu lực", format dd-mm-yyyy
    trich_yeu: Optional[str] = None          # "Trích yếu" (title)
    is_effective_by_date: Optional[bool] = None  # None if ngay_hieu_luc missing/unparseable
    note: str = ""


def _fetch(url: str, method: str = "GET", data: dict | None = None) -> httpx.Response:
    with httpx.Client(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
        resp = client.request(method, url, data=data)
    resp.raise_for_status()
    return resp


def _collect_form_fields(soup: BeautifulSoup) -> dict:
    """Snapshot every current form field's value, for ASP.NET postback replay."""
    fields = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        if inp.get("type") in ("checkbox", "radio") and not inp.get("checked"):
            continue
        fields[name] = inp.get("value", "")
    for sel in soup.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        selected = sel.find("option", selected=True) or sel.find("option")
        fields[name] = selected.get("value", "") if selected else ""
    for ta in soup.find_all("textarea"):
        name = ta.get("name")
        if name:
            fields[name] = ta.get_text()
    return fields


def _postback(url: str, soup: BeautifulSoup, event_target: str, event_argument: str) -> BeautifulSoup:
    """Replay the page's current form state with an updated __EVENTTARGET /
    __EVENTARGUMENT, simulating an ASP.NET __doPostBack() pagination click.
    """
    fields = _collect_form_fields(soup)
    fields["__EVENTTARGET"] = event_target
    fields["__EVENTARGUMENT"] = event_argument
    resp = _fetch(url, method="POST", data=fields)
    return BeautifulSoup(resp.text, "lxml")


def _parse_listing_rows(soup: BeautifulSoup) -> list[dict]:
    """Extract (so_hieu, url, ngay_ban_hanh, trich_yeu) from a listing page's
    result table. Matches on the URL pattern (?pageid=27160&docid=...)
    rather than a CSS class, since that pattern was confirmed live and is
    more likely to survive a redesign than a specific class name.
    """
    rows = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "pageid=27160" not in href or "docid=" not in href:
            continue
        text = a.get_text(strip=True)
        # Row link text on the listing page is "{so_hieu} {ngay_ban_hanh}"
        # e.g. "108/2025/QH15 10/12/2025" — split on the last whitespace run
        # that looks like a date.
        m = re.match(r"^(?P<so_hieu>\S+)\s+(?P<ngay>\d{2}/\d{2}/\d{4})$", text)
        if not m:
            continue
        rows.append({
            "so_hieu": m.group("so_hieu"),
            "ngay_ban_hanh": m.group("ngay"),
            "url": urljoin(BASE_URL, href),
        })
    return rows


def _parse_detail_attributes(soup: BeautifulSoup) -> dict:
    """Parse the Số ký hiệu / Ngày ban hành / Ngày có hiệu lực / ... table
    on a document detail page. See module docstring — no status field
    exists here, only dates and metadata.
    """
    attrs = {}
    known_labels = {
        "Số ký hiệu", "Ngày ban hành", "Ngày có hiệu lực", "Loại văn bản",
        "Cơ quan ban hành", "Người ký", "Trích yếu",
    }
    for row in soup.find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) >= 2 and cells[0] in known_labels:
            attrs[cells[0]] = cells[1]
    return attrs


def _is_past(date_str: str) -> Optional[bool]:
    """Parse a dd-mm-yyyy date and compare to today. Returns None if unparseable."""
    for fmt in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date() <= datetime.now().date()
        except ValueError:
            continue
    return None


def check_effective_status(so_hieu: str, max_pages: int = 30) -> EffectiveStatusResult:
    """Search the Luật - Pháp lệnh registry for a document by its Số hiệu
    (e.g. "45/2019/QH14") and return what vanban.chinhphu.vn can confirm
    about it. This is the main entry point other modules should call —
    see the module docstring for what this can and can't tell you.
    """
    url = LAW_LIST_URL
    resp = _fetch(url)
    soup = BeautifulSoup(resp.text, "lxml")

    for page in range(1, max_pages + 1):
        for row in _parse_listing_rows(soup):
            if row["so_hieu"] == so_hieu:
                detail_resp = _fetch(row["url"])
                detail_soup = BeautifulSoup(detail_resp.text, "lxml")
                attrs = _parse_detail_attributes(detail_soup)
                ngay_hieu_luc = attrs.get("Ngày có hiệu lực")
                return EffectiveStatusResult(
                    so_hieu=so_hieu,
                    found=True,
                    url=row["url"],
                    ngay_ban_hanh=attrs.get("Ngày ban hành"),
                    ngay_hieu_luc=ngay_hieu_luc,
                    trich_yeu=attrs.get("Trích yếu"),
                    is_effective_by_date=_is_past(ngay_hieu_luc) if ngay_hieu_luc else None,
                    note="Confirmed present in Government registry. This source has no "
                         "repeal/status field — cross-check against thuvienphapluat.vn's "
                         "'Tình trạng' for that.",
                )

        if page >= max_pages:
            break
        try:
            soup = _postback(url, soup, GRID_CONTROL_ID, f"Page${page + 1}")
        except httpx.HTTPError as e:
            logger.error("Pagination postback failed on page %d: %s", page, e)
            break

    return EffectiveStatusResult(
        so_hieu=so_hieu,
        found=False,
        note=f"Not found within {max_pages} pages of the Luật - Pháp lệnh registry. "
             f"Could mean the number is wrong, it's genuinely not registered here, "
             f"or max_pages needs raising for an older law.",
    )


if __name__ == "__main__":
    # Manual smoke test: python -m crawler.sources.vanban_chinhphu
    logging.basicConfig(level=logging.INFO)
    # 45/2019/QH14 = Bộ luật Lao động 2019 — deliberately not on page 1
    # (sorted newest-first), so this also exercises pagination.
    result = check_effective_status("45/2019/QH14", max_pages=10)
    print(result)
