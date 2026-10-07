"""Self-checks for crawler logic that needs no network or models.

Run from crawler/:  python -m tests.test_logic
"""

from types import SimpleNamespace

from crawler.chunker import _split_by_diem, _split_by_khoan, chunk_by_article
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
    # Consolidated texts drop repealed Khoản: 1, 2, 4 is still a real run.
    assert [n for n, _ in _split_by_khoan("1. A.\n2. B.\n4. D.")[1]] == ["1", "2", "4"]


def test_long_khoan_split_by_diem() -> None:
    points = "\n".join(f"{x}) Trường hợp {x}: " + "nội dung " * 60 for x in "abcdđeg")
    md = f"### Điều 9. Chi phí\n\n1. Ngắn.\n2. Các khoản chi sau:\n{points}\n"
    chunks = chunk_by_article(SimpleNamespace(markdown=md, law_name="NĐ", source_url="u"))
    labels = [c.metadata.khoan for c in chunks]
    assert labels[:3] == ["Khoản 1", "Khoản 2, điểm a", "Khoản 2, điểm b"] and len(set(labels)) == 8
    assert "Các khoản chi sau:" in chunks[5].text and "đ) Trường hợp đ" in chunks[5].text
    assert _split_by_diem("a) X.\nc) Y.\nb) Z.") == ("", [])  # out of order: keep whole


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


def test_vbhn_btc_footnotes_and_signature() -> None:
    # Markup seen live on VBHN-BTC decree pages (2026-10-03).
    page = ('<div id="noidung"><div class="the-document-body">'
            '<p>Điều 8. Nguyên tắc</p><p><span>doanh thu từ 01 tỷ đồng<sup>2</sup></span>'
            '<span id="footnote-ref-2"></span><span> trở xuống, diện tích 30 m<sup>2</sup>.</span></p>'
            '<p id="footnote-2"><sup>2</sup> Cụm từ “500 triệu đồng” được thay thế</p>'
            '<table><tr><td><p>BỘ TÀI CHÍNH</p><p><b>Nơi nhận:</b> - Văn phòng Chính phủ</p></td></tr></table>'
            '<p>Phụ lục I</p><p>Điều 1. Không phải Điều của văn bản</p></div></div>')
    page = page.replace("<p>Điều 8. Nguyên tắc</p>", "<p><b>Điều 7.</b><b><sup>28</sup></b> Xử phạt</p>"
                        "<p>Mỗi năm<sup>3</sup> nộp một lần, kho 20m<sup>3</sup>.</p><p>Điều 8. Nguyên tắc</p>")
    doc = SimpleNamespace(law_name="NĐ", url="u", raw_html=extract_law_html(page))
    md = parse_to_markdown(doc).markdown
    assert "### Điều 7. Xử phạt" in md.splitlines()
    assert "Mỗi năm nộp một lần, kho 20m3." in md.splitlines()
    assert "doanh thu từ 01 tỷ đồng trở xuống, diện tích 30 m2." in md.splitlines()
    assert "500 triệu" not in md and "Phụ lục" not in md and "BỘ TÀI CHÍNH" not in md


if __name__ == "__main__":
    test_vbhn_btc_footnotes_and_signature()
    test_extract_law_html_strips_noise()
    test_parse_to_markdown_headings()
    test_split_by_khoan()
    test_long_khoan_split_by_diem()
    test_parse_strips_vbhn_footnote_numbers()
    test_parse_keeps_table_rows_together()
    test_parse_stops_at_signature_block()
    print("crawler logic OK")
