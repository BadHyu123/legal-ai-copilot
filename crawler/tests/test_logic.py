"""Self-checks for crawler logic that needs no network or models.

Run from crawler/:  python -m tests.test_logic
"""

from types import SimpleNamespace

from crawler.chunker import _split_by_khoan, chunk_by_article
from crawler.parser import parse_to_markdown
from crawler.sources.luatvietnam import extract_law_html

# Mirrors markup seen live on luatvietnam.vn: inline tags inside words and
# sentences, the "Đang theo dõi" tooltip after each paragraph, an editorial
# note, "Chương I." / same-line "Chương VI TIỀN LƯƠNG", "Mục 1 GIAO KẾT"
# without a period, and "Điều 66 ." with a space before the period.
PAGE = """
<div id="noidung"><div class="the-document-body">
  <div class="docitem-1"><p>B<span>Ộ</span> LUẬT LAO ĐỘNG</p></div>
  <div class="docitem-2"><p>Chương I.</p><p>NHỮNG QUY ĐỊNH CHUNG</p>
    <span class="tooltip-button"><span class="bg-theo-doi">Đang theo dõi</span></span></div>
  <div class="docitem-5"><p><b>Điều 1. Phạm vi điều chỉnh</b></p>
    <p>Bộ luật này quy định theo <a href="#">Điều 29</a> của Bộ luật này.</p></div>
  <div class="docitem-binhluan">Theo quy định tại Nghị quyết số 66.18/2026/NQ-CP ...</div>
  <div class="docitem-2"><p>Chương VI TIỀN LƯƠNG</p></div>
  <div class="docitem-3"><p>Mục 1 GIAO KẾT HỢP ĐỒNG</p></div>
  <div class="docitem-5"><p><b>Điều 66</b> . Nguyên tắc thương lượng tập thể</p>
    <p>1. Tự nguyện.</p><p>2. Thiện chí.</p></div>
  <div class="docitem-3"><p>Mục 2 của Chương này được áp dụng tương tự.</p></div>
</div></div>
"""


def test_extract_law_html_strips_noise() -> None:
    html = extract_law_html(PAGE)
    assert "Đang theo dõi" not in html and "66.18/2026" not in html
    assert "Điều 1" in html
    assert extract_law_html("<html><body>redesigned</body></html>") == ""


def test_parse_to_markdown_headings() -> None:
    doc = SimpleNamespace(law_name="BLLĐ", url="u", raw_html=extract_law_html(PAGE))
    md = parse_to_markdown(doc).markdown
    lines = md.splitlines()
    assert "# Chương I. NHỮNG QUY ĐỊNH CHUNG" in lines
    assert "# Chương VI. TIỀN LƯƠNG" in lines
    assert "## Mục 1. GIAO KẾT HỢP ĐỒNG" in lines
    assert "### Điều 1. Phạm vi điều chỉnh" in lines
    assert "### Điều 66. Nguyên tắc thương lượng tập thể" in lines
    # Inline tags no longer split words or sentences.
    assert "BỘ LUẬT LAO ĐỘNG" in lines
    assert "Bộ luật này quy định theo Điều 29 của Bộ luật này." in lines
    # A body line starting "Mục 2 của..." is a cross-reference, not a heading.
    assert "Mục 2 của Chương này được áp dụng tương tự." in lines

    chunks = chunk_by_article(SimpleNamespace(markdown=md, law_name="BLLĐ", source_url="u"))
    assert [c.metadata.dieu for c in chunks] == ["Điều 1", "Điều 66"]


def test_split_by_khoan() -> None:
    # Lead-in ending in ":" before Khoản 1 is kept as the intro (the old
    # rule missed "1." after a colon and dropped intro + Khoản 1 entirely).
    body = ("Thu nhập chịu thuế gồm các loại sau đây:\n1. Thu nhập từ kinh doanh.\n"
            "1a.21 Thu nhập bổ sung.\n21 Khoản này được bổ sung theo Luật số 133/2025/QH15.\n"
            "2. Thu nhập từ tiền lương, chiếm 100% thu nhập.")
    intro, segments = _split_by_khoan(body)
    assert intro == "Thu nhập chịu thuế gồm các loại sau đây:"
    assert [n for n, _ in segments] == ["1", "1a", "2"]
    assert segments[1][1].startswith("Thu nhập bổ sung.")  # footnote number stripped
    assert "Luật số 133/2025/QH15" in segments[1][1]       # footnote text kept

    # Numbers mid-sentence (day counts, percentages) are not boundaries.
    assert _split_by_khoan("Nghỉ 6 tháng. Hưởng 100 % lương trong 30 ngày.") == ("", [])

    # A numbered list inside Khoản 2 restarts at 1 -> not sequential -> keep whole.
    nested = "1. Quyền chung.\n2. Gồm các trường hợp sau:\n1. Ốm đau.\n2. Thai sản."
    assert _split_by_khoan(nested) == ("", [])


def test_parse_strips_vbhn_footnote_numbers() -> None:
    html = ("<p>Điều 139. Nghỉ thai sản</p><p>1.<sup>4</sup><a>[4]</a> Lao động nữ được nghỉ 06 tháng.</p>"
            "<p>1a.21 Khoản bổ sung.</p><p>1.000.000 đồng là mức phạt.</p>")
    lines = parse_to_markdown(SimpleNamespace(law_name="L", url="u", raw_html=html)).markdown.splitlines()
    assert "1. Lao động nữ được nghỉ 06 tháng." in lines
    assert "1a. Khoản bổ sung." in lines
    assert "1.000.000 đồng là mức phạt." in lines  # an amount, not a footnote


def test_parse_keeps_table_rows_together() -> None:
    html = ("<p>Điều 9. Biểu thuế lũy tiến từng phần</p><table>"
            "<tr><td><p>Bậc thuế</p></td><td><p>Phần thu nhập tính</p><p>thuế/năm</p></td><td>Thuế suất</td></tr>"
            "<tr><td>1</td><td>Đến 120</td><td>5</td></tr></table>")
    lines = parse_to_markdown(SimpleNamespace(law_name="L", url="u", raw_html=html)).markdown.splitlines()
    assert "Bậc thuế | Phần thu nhập tính thuế/năm | Thuế suất" in lines
    assert "1 | Đến 120 | 5" in lines


def test_parse_stops_at_signature_block() -> None:
    html = ("<p>Điều 1. Hiệu lực</p><p>Luật này có hiệu lực.</p><p>__________</p>"
            "<p>CHỦ NHIỆM</p><p>Điều 5. Hiệu lực thi hành</p>")  # footnote quoting another law
    md = parse_to_markdown(SimpleNamespace(law_name="L", url="u", raw_html=html)).markdown
    assert "CHỦ NHIỆM" not in md and "Điều 5" not in md


if __name__ == "__main__":
    test_extract_law_html_strips_noise()
    test_parse_to_markdown_headings()
    test_split_by_khoan()
    test_parse_strips_vbhn_footnote_numbers()
    test_parse_keeps_table_rows_together()
    test_parse_stops_at_signature_block()
    print("crawler logic OK")
