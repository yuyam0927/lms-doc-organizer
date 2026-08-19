import json
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .parsers._markdown import escape_cell

_FORBIDDEN_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_TRAILING_DOTS_SPACES = re.compile(r"[.\s]+$")
_DATE_FORMAT = "%Y-%m-%d"
_MAX_TITLE_LENGTH = 60
_REPORT_HEADER_PREFIX = "# ファイル整理レポート"


class ManifestError(Exception):
    """Raised when the manifest file is malformed."""


@dataclass
class PlanEntry:
    source: Path
    target: Path
    year_month: str


def _sanitize_title(title: str) -> str:
    title = _FORBIDDEN_CHARS.sub("_", title).strip()
    title = _TRAILING_DOTS_SPACES.sub("", title)
    title = title[:_MAX_TITLE_LENGTH]
    title = _TRAILING_DOTS_SPACES.sub("", title)
    return title or "無題"


def _resolve_date(entry: dict, source: Path) -> date:
    if "date" not in entry or entry["date"] is None:
        return datetime.fromtimestamp(source.stat().st_mtime).date()
    raw = entry["date"]
    if not isinstance(raw, str) or not raw:
        raise ManifestError(f"'date' must be a non-empty string in YYYY-MM-DD format: {raw!r}")
    try:
        return datetime.strptime(raw, _DATE_FORMAT).date()
    except ValueError as exc:
        raise ManifestError(f"'date' is not a valid YYYY-MM-DD date: {raw!r}") from exc


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
        raw_text = manifest_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ManifestError(f"failed to read manifest: {exc}") from exc

    try:
        entries = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc

    if not isinstance(entries, list):
        raise ManifestError("manifest must be a JSON array")

    base_resolved = base_dir.resolve()

    plan: list[PlanEntry] = []
    taken: set[Path] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ManifestError(f"manifest entry must be a JSON object: {entry!r}")
        if not isinstance(entry.get("source"), str) or not isinstance(entry.get("title"), str):
            raise ManifestError(f"manifest entry missing/invalid 'source' or 'title' (must be strings): {entry!r}")

        source = Path(entry["source"])
        if not source.is_file():
            raise ManifestError(f"source file not found: {source}")

        source_resolved = source.resolve()
        if source_resolved != base_resolved and base_resolved not in source_resolved.parents:
            raise ManifestError(
                f"source is outside of base-dir and was rejected: {source} (base-dir: {base_dir})"
            )

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
        lines.append(
            f"| {escape_cell(entry.source.name)} | {escape_cell(entry.target.name)} | {entry.year_month} |"
        )
    return "\n".join(lines)


def _backup_foreign_report(report_path: Path) -> None:
    """If report_path exists and wasn't written by a previous run of this tool,
    move it aside instead of silently overwriting the user's file."""
    if not report_path.exists():
        return
    try:
        existing = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        existing = ""
    if existing.startswith(_REPORT_HEADER_PREFIX):
        return

    backup_path = report_path.with_name(report_path.name + ".bak")
    counter = 2
    while backup_path.exists():
        backup_path = report_path.with_name(f"{report_path.name}.bak{counter}")
        counter += 1
    report_path.replace(backup_path)


def apply_plan(plan: list[PlanEntry], report_path: Path, base_dir: Path) -> tuple[int, str | None]:
    """Move each entry's source to its target, writing a report.

    Returns (failures, report_error): `failures` is the number of entries that
    failed to move (0 means all moves succeeded); `report_error` is None on
    success or a message describing why the report could not be written.
    """
    base_resolved = base_dir.resolve()
    results = []
    taken: set[Path] = set()
    failures = 0

    for entry in plan:
        target = entry.target
        if target.exists() or target in taken:
            # Filesystem state drifted since the plan was built (e.g. time
            # elapsed between the dry-run preview and this --apply run).
            target = _avoid_collision(target, taken)
        taken.add(target)

        note = "" if target == entry.target else f"衝突のため名称変更: {target.name}"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target_resolved_parent = target.parent.resolve()
            if target_resolved_parent != base_resolved and base_resolved not in target_resolved_parent.parents:
                raise OSError(f"resolved target escapes base-dir: {target}")
            shutil.move(str(entry.source), str(target))
            results.append((entry, target, "完了", note))
        except OSError as exc:
            failures += 1
            detail = f"{note}; {exc}" if note else str(exc)
            results.append((entry, target, "失敗", detail))

    lines = [
        f"{_REPORT_HEADER_PREFIX} {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| 元ファイル名 | 新ファイル名 | 移動先フォルダ | 状態 | 備考 |",
        "|---|---|---|---|---|",
    ]
    for entry, target, status, note in results:
        lines.append(
            f"| {escape_cell(entry.source.name)} | {escape_cell(target.name)} | {entry.year_month} "
            f"| {status} | {escape_cell(note)} |"
        )

    report_error: str | None = None
    try:
        _backup_foreign_report(report_path)
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        report_error = str(exc)

    return failures, report_error
