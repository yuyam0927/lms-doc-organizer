from pathlib import Path


def text_to_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")
