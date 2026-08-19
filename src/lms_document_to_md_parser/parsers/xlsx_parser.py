from pathlib import Path

from openpyxl import load_workbook


def _row_to_cells(row) -> list[str]:
    return ["" if cell is None else str(cell) for cell in row]


def xlsx_to_markdown(path: Path) -> str:
    workbook = load_workbook(str(path), data_only=True, read_only=True)
    parts: list[str] = []

    for sheet in workbook.worksheets:
        rows = [_row_to_cells(row) for row in sheet.iter_rows(values_only=True)]
        rows = [row for row in rows if any(cell.strip() for cell in row)]
        if not rows:
            continue

        width = max(len(row) for row in rows)
        rows = [row + [""] * (width - len(row)) for row in rows]

        header, *body = rows
        lines = [f"## {sheet.title}", ""]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")
        for row in body:
            lines.append("| " + " | ".join(row) + " |")
        parts.append("\n".join(lines))

    return "\n\n".join(parts) + "\n"
