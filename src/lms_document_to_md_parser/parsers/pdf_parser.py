import bisect
from pathlib import Path

import pdfplumber

from ._markdown import rows_to_table


class UnextractablePdfError(Exception):
    """Raised when a PDF has no extractable text (e.g. scanned images without OCR)."""


def _table_bbox_filter(table_bboxes: list[tuple[float, float, float, float]]):
    def keep(obj) -> bool:
        x0, top, x1, bottom = obj["x0"], obj["top"], obj["x1"], obj["bottom"]
        for bx0, btop, bx1, bbottom in table_bboxes:
            if bx0 <= x0 and x1 <= bx1 and btop <= top and bottom <= bbottom:
                return False
        return True

    return keep


def _normalize_table_rows(rows: list[list[str | None]]) -> list[list[str]]:
    # pdfplumber represents empty cells as None, not "".
    return [[(cell or "").strip() for cell in row] for row in rows]


def _extract_page_blocks(page) -> list[str]:
    """Return the page's text paragraphs and tables as Markdown blocks, ordered
    top-to-bottom to match the page layout (instead of all text, then all
    tables). Table regions are excluded from the text so content isn't
    duplicated between the two."""
    tables = page.find_tables()
    table_bboxes = [t.bbox for t in tables]

    items: list[tuple[float, str]] = []
    for table, bbox in zip(tables, table_bboxes):
        md = rows_to_table(_normalize_table_rows(table.extract()))
        if md:
            items.append((bbox[1], md))

    text_page = page.filter(_table_bbox_filter(table_bboxes)) if table_bboxes else page
    table_tops = sorted(bbox[1] for bbox in table_bboxes)

    buffer: list[str] = []
    buffer_top: float | None = None
    prev_band: int | None = None
    for line in sorted(text_page.extract_text_lines(), key=lambda line: line["top"]):
        text = line["text"].strip()
        if not text:
            continue
        band = bisect.bisect_right(table_tops, line["top"])
        if prev_band is not None and band != prev_band and buffer:
            items.append((buffer_top, "\n".join(buffer)))
            buffer, buffer_top = [], None
        if buffer_top is None:
            buffer_top = line["top"]
        buffer.append(text)
        prev_band = band
    if buffer:
        items.append((buffer_top, "\n".join(buffer)))

    items.sort(key=lambda item: item[0])
    return [content for _, content in items]


def pdf_to_markdown(path: Path) -> str:
    parts: list[str] = []
    any_content = False
    with pdfplumber.open(str(path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            blocks = _extract_page_blocks(page)
            if not blocks:
                parts.append(f"## Page {page_number}\n\n*(テキストを抽出できませんでした。スキャン画像の可能性があります)*")
                continue

            any_content = True
            parts.append(f"## Page {page_number}")
            parts.extend(blocks)

    if not any_content:
        raise UnextractablePdfError(
            f"{path.name}: no extractable text (likely a scanned image PDF; OCR not supported)"
        )
    return "\n\n".join(parts) + "\n"
