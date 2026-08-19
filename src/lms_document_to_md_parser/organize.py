import json
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

_FORBIDDEN_CHARS = re.compile(r'[\\/:*?"<>|]')
_MAX_TITLE_LENGTH = 60


class ManifestError(Exception):
    """Raised when the manifest file is malformed."""


@dataclass
class PlanEntry:
    source: Path
    target: Path
    year_month: str


def _sanitize_title(title: str) -> str:
    title = _FORBIDDEN_CHARS.sub("_", title).strip()
    title = title or "無題"
    return title[:_MAX_TITLE_LENGTH]


def _resolve_date(entry: dict, source: Path) -> date:
    raw = entry.get("date")
    if raw:
        try:
            return datetime.fromisoformat(raw).date()
        except ValueError:
            pass
    return datetime.fromtimestamp(source.stat().st_mtime).date()


def _avoid_collision(path: Path, taken: set[Path]) -> Path:
    if path not in taken and not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if candidate not in taken and not candidate.exists():
            return candidate
        counter += 1


def build_plan(manifest_path: Path, base_dir: Path) -> list[PlanEntry]:
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc

    if not isinstance(entries, list):
        raise ManifestError("manifest must be a JSON array")

    plan: list[PlanEntry] = []
    taken: set[Path] = set()
    for entry in entries:
        if "source" not in entry or "title" not in entry:
            raise ManifestError(f"manifest entry missing 'source' or 'title': {entry}")

        source = Path(entry["source"])
        if not source.is_file():
            raise ManifestError(f"source file not found: {source}")

        entry_date = _resolve_date(entry, source)
        title = _sanitize_title(entry["title"])
        year_month = entry_date.strftime("%Y-%m")
        new_name = f"{entry_date.strftime('%Y%m%d')}_{title}{source.suffix}"

        target_dir = base_dir / year_month
        target = _avoid_collision(target_dir / new_name, taken)
        taken.add(target)
        plan.append(PlanEntry(source=source, target=target, year_month=year_month))

    return plan


def format_preview(plan: list[PlanEntry]) -> str:
    lines = ["| 元ファイル名 | 新ファイル名 | 移動先フォルダ |", "|---|---|---|"]
    for entry in plan:
        lines.append(f"| {entry.source.name} | {entry.target.name} | {entry.year_month} |")
    return "\n".join(lines)


def apply_plan(plan: list[PlanEntry], report_path: Path) -> None:
    results = []
    for entry in plan:
        entry.target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(entry.source), str(entry.target))
            results.append((entry, "完了", ""))
        except OSError as exc:
            results.append((entry, "失敗", str(exc)))

    lines = [
        f"# ファイル整理レポート {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| 元ファイル名 | 新ファイル名 | 移動先フォルダ | 状態 | 備考 |",
        "|---|---|---|---|---|",
    ]
    for entry, status, note in results:
        lines.append(f"| {entry.source.name} | {entry.target.name} | {entry.year_month} | {status} | {note} |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
