from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def _iter_block_items(parent):
    """Yield paragraphs and tables in document order."""
    for child in parent.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, parent)
        elif child.tag.endswith("}tbl"):
            yield Table(child, parent)


def _paragraph_to_md(paragraph: Paragraph) -> str:
    text = paragraph.text.strip()
    if not text:
        return ""

    style = (paragraph.style.name or "").lower()
    if style.startswith("heading"):
        try:
            level = int(style.split(" ")[-1])
        except ValueError:
            level = 1
        level = max(1, min(level, 6))
        return f"{'#' * level} {text}"
    if style.startswith("list"):
        return f"- {text}"
    return text


def _table_to_md(table: Table) -> str:
    rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
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


def docx_to_markdown(path: Path) -> str:
    document = Document(str(path))
    parts: list[str] = []
    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            md = _paragraph_to_md(block)
        else:
            md = _table_to_md(block)
        if md:
            parts.append(md)
    return "\n\n".join(parts) + "\n"
