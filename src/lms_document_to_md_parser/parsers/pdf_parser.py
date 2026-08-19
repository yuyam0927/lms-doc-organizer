from pathlib import Path

import pdfplumber


class UnextractablePdfError(Exception):
    """Raised when a PDF has no extractable text (e.g. scanned images without OCR)."""


def _table_to_md(table: list[list[str | None]]) -> str:
    rows = [[(cell or "").strip() for cell in row] for row in table]
    if not rows:
        return ""
    header, *body = rows
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def pdf_to_markdown(path: Path) -> str:
    parts: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            tables = [_table_to_md(t) for t in page.extract_tables()]
            tables = [t for t in tables if t]
            if not text and not tables:
                continue
            parts.append(f"## Page {page_number}")
            if text:
                parts.append(text)
            parts.extend(tables)

    if not parts:
        raise UnextractablePdfError(
            f"{path.name}: no extractable text (likely a scanned image PDF; OCR not supported)"
        )
    return "\n\n".join(parts) + "\n"
