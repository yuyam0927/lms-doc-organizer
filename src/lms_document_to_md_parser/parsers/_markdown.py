"""Shared helpers for rendering Markdown tables from parsed cell data."""


def escape_cell(text: str) -> str:
    """Escape characters that would otherwise break a Markdown table cell."""
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def rows_to_table(rows: list[list[str]]) -> str:
    """Render rows (first row = header) as a GitHub-flavored Markdown table."""
    if not rows:
        return ""
    header, *body = [[escape_cell(cell) for cell in row] for row in rows]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
