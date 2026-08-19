import pytest

import lms_document_to_md_parser.parsers.pdf_parser as pdf_parser
from lms_document_to_md_parser.parsers.pdf_parser import (
    UnextractablePdfError,
    _table_bbox_filter,
    pdf_to_markdown,
)


class FakeTable:
    def __init__(self, bbox, rows):
        self.bbox = bbox
        self._rows = rows

    def extract(self):
        return self._rows


def _line(top: float, text: str, x0: float = 10.0, x1: float = 40.0, bottom: float | None = None) -> dict:
    return {"top": top, "text": text, "x0": x0, "x1": x1, "bottom": top + 10 if bottom is None else bottom}


class FakePage:
    """Mimics the subset of pdfplumber's Page API used by pdf_parser: unlike a
    naive stub, `filter()` actually applies the predicate to the stored lines
    (matching real pdfplumber behavior), so table/text de-duplication is
    genuinely exercised rather than assumed."""

    def __init__(self, lines=None, tables=None):
        self._lines = lines or []
        self._tables = tables or []

    def find_tables(self):
        return self._tables

    def filter(self, predicate):
        return FakePage(lines=[line for line in self._lines if predicate(line)], tables=self._tables)

    def extract_text_lines(self):
        return self._lines


class FakePDF:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _patch_pdfplumber(monkeypatch, pages):
    monkeypatch.setattr(pdf_parser.pdfplumber, "open", lambda path: FakePDF(pages))


def test_table_bbox_filter_excludes_only_chars_inside_bbox():
    keep = _table_bbox_filter([(0, 0, 10, 10)])
    inside = {"x0": 1, "top": 1, "x1": 9, "bottom": 9}
    outside = {"x0": 20, "top": 20, "x1": 25, "bottom": 25}
    assert keep(inside) is False
    assert keep(outside) is True


def test_pdf_to_markdown_renders_text_and_escaped_table(monkeypatch, tmp_path):
    table = FakeTable((0, 0, 100, 10), [["h1", "h2"], ["a|b", "c"]])
    page = FakePage(lines=[_line(20, "本文テキスト")], tables=[table])
    _patch_pdfplumber(monkeypatch, [page])

    md = pdf_to_markdown(tmp_path / "sample.pdf")

    assert "## Page 1" in md
    assert "本文テキスト" in md
    assert "| a\\|b | c |" in md


def test_pdf_to_markdown_preserves_document_order_and_avoids_duplication(monkeypatch, tmp_path):
    table = FakeTable((0, 50, 100, 70), [["h1", "h2"], ["v1", "v2"]])
    lines = [
        _line(10, "段落1 行1"),
        _line(20, "段落1 行2"),
        _line(55, "表の中の文字 (除外されるべき)"),  # falls inside the table bbox
        _line(80, "段落2"),
    ]
    page = FakePage(lines=lines, tables=[table])
    _patch_pdfplumber(monkeypatch, [page])

    md = pdf_to_markdown(tmp_path / "sample.pdf")

    assert "表の中の文字" not in md
    para1_pos = md.index("段落1 行1")
    table_pos = md.index("| v1 | v2 |")
    para2_pos = md.index("段落2")
    assert para1_pos < table_pos < para2_pos
    assert "段落1 行1\n段落1 行2" in md


def test_pdf_to_markdown_handles_none_cells_in_table(monkeypatch, tmp_path):
    # pdfplumber represents empty table cells as None, not "".
    table = FakeTable((0, 0, 100, 10), [["h1", "h2"], [None, "c"]])
    page = FakePage(lines=[], tables=[table])
    _patch_pdfplumber(monkeypatch, [page])

    md = pdf_to_markdown(tmp_path / "sample.pdf")

    assert "|  | c |" in md


def test_pdf_to_markdown_marks_page_without_extractable_text(monkeypatch, tmp_path):
    pages = [FakePage(lines=[_line(10, "ページ1")]), FakePage(lines=[])]
    _patch_pdfplumber(monkeypatch, pages)

    md = pdf_to_markdown(tmp_path / "sample.pdf")

    assert "## Page 1" in md
    assert "ページ1" in md
    assert "## Page 2" in md
    assert "テキストを抽出できませんでした" in md


def test_pdf_to_markdown_raises_when_all_pages_empty(monkeypatch, tmp_path):
    _patch_pdfplumber(monkeypatch, [FakePage(lines=[]), FakePage(lines=[])])

    with pytest.raises(UnextractablePdfError):
        pdf_to_markdown(tmp_path / "scanned.pdf")
