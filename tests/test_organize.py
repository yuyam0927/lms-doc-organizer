import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from lms_document_to_md_parser.organize import (
    ManifestError,
    PlanEntry,
    apply_plan,
    build_plan,
    format_preview,
)


def _write_manifest(tmp_path: Path, entries) -> Path:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def _make_source(tmp_path: Path, name: str) -> Path:
    source = tmp_path / name
    source.write_text("dummy", encoding="utf-8")
    return source


# ---- build_plan: happy paths ----------------------------------------------


def test_build_plan_uses_explicit_date(tmp_path):
    source = _make_source(tmp_path, "report.txt")
    manifest = _write_manifest(
        tmp_path, [{"source": str(source), "title": "レポート", "date": "2026-08-19"}]
    )

    plan = build_plan(manifest, tmp_path)

    assert len(plan) == 1
    entry = plan[0]
    assert entry.year_month == "2026-08"
    assert entry.target.name == "20260819_レポート.txt"
    assert entry.target.parent == tmp_path / "2026-08"


def test_build_plan_falls_back_to_mtime_when_date_omitted(tmp_path):
    source = _make_source(tmp_path, "report.txt")
    mtime = datetime(2025, 1, 15).timestamp()
    os.utime(source, (mtime, mtime))
    manifest = _write_manifest(tmp_path, [{"source": str(source), "title": "レポート"}])

    plan = build_plan(manifest, tmp_path)

    assert plan[0].year_month == "2025-01"
    assert plan[0].target.name == "20250115_レポート.txt"


def test_build_plan_avoids_collisions_between_entries(tmp_path):
    source1 = _make_source(tmp_path, "a.txt")
    source2 = _make_source(tmp_path, "b.txt")
    manifest = _write_manifest(
        tmp_path,
        [
            {"source": str(source1), "title": "同じ", "date": "2026-08-19"},
            {"source": str(source2), "title": "同じ", "date": "2026-08-19"},
        ],
    )

    plan = build_plan(manifest, tmp_path)

    names = {entry.target.name for entry in plan}
    assert names == {"20260819_同じ.txt", "20260819_同じ_2.txt"}


# ---- build_plan: validation / error paths ----------------------------------


def test_build_plan_rejects_invalid_json(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("not json", encoding="utf-8")

    with pytest.raises(ManifestError):
        build_plan(manifest, tmp_path)


def test_build_plan_rejects_non_array_manifest(tmp_path):
    manifest = _write_manifest(tmp_path, {"not": "a list"})

    with pytest.raises(ManifestError):
        build_plan(manifest, tmp_path)


def test_build_plan_rejects_non_dict_entry(tmp_path):
    manifest = _write_manifest(tmp_path, ["just-a-string"])

    with pytest.raises(ManifestError):
        build_plan(manifest, tmp_path)


def test_build_plan_rejects_missing_required_fields(tmp_path):
    manifest = _write_manifest(tmp_path, [{"title": "タイトルのみ"}])

    with pytest.raises(ManifestError):
        build_plan(manifest, tmp_path)


def test_build_plan_rejects_non_string_source_or_title(tmp_path):
    manifest = _write_manifest(tmp_path, [{"source": 123, "title": "レポート"}])

    with pytest.raises(ManifestError):
        build_plan(manifest, tmp_path)


def test_build_plan_rejects_missing_source_file(tmp_path):
    manifest = _write_manifest(
        tmp_path, [{"source": str(tmp_path / "missing.txt"), "title": "レポート"}]
    )

    with pytest.raises(ManifestError):
        build_plan(manifest, tmp_path)


def test_build_plan_rejects_malformed_date(tmp_path):
    source = _make_source(tmp_path, "report.txt")
    manifest = _write_manifest(
        tmp_path, [{"source": str(source), "title": "レポート", "date": "not-a-date"}]
    )

    with pytest.raises(ManifestError):
        build_plan(manifest, tmp_path)


def test_build_plan_rejects_non_string_date(tmp_path):
    source = _make_source(tmp_path, "report.txt")
    manifest = _write_manifest(
        tmp_path, [{"source": str(source), "title": "レポート", "date": 20260819}]
    )

    with pytest.raises(ManifestError):
        build_plan(manifest, tmp_path)


def test_build_plan_rejects_falsy_non_string_date(tmp_path):
    source = _make_source(tmp_path, "report.txt")
    manifest = _write_manifest(tmp_path, [{"source": str(source), "title": "レポート", "date": 0}])

    with pytest.raises(ManifestError):
        build_plan(manifest, tmp_path)


def test_build_plan_treats_null_date_as_omitted(tmp_path):
    source = _make_source(tmp_path, "report.txt")
    mtime = datetime(2025, 1, 15).timestamp()
    os.utime(source, (mtime, mtime))
    manifest = _write_manifest(tmp_path, [{"source": str(source), "title": "レポート", "date": None}])

    plan = build_plan(manifest, tmp_path)

    assert plan[0].year_month == "2025-01"


def test_build_plan_wraps_manifest_read_errors(tmp_path):
    # A directory can't be read as a file; read_text() raises OSError.
    manifest_dir = tmp_path / "manifest.json"
    manifest_dir.mkdir()

    with pytest.raises(ManifestError):
        build_plan(manifest_dir, tmp_path)


def test_build_plan_rejects_source_outside_base_dir(tmp_path):
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    source = _make_source(outside_dir, "secret.txt")
    manifest = _write_manifest(tmp_path, [{"source": str(source), "title": "外部"}])

    with pytest.raises(ManifestError):
        build_plan(manifest, base_dir)


# ---- format_preview ----------------------------------------------------


def test_format_preview_renders_markdown_table():
    plan = [PlanEntry(source=Path("a.txt"), target=Path("2026-08/20260819_a.txt"), year_month="2026-08")]

    preview = format_preview(plan)

    assert "| a.txt | 20260819_a.txt | 2026-08 |" in preview


# ---- apply_plan ----------------------------------------------------------


def test_apply_plan_moves_files_and_reports_success(tmp_path):
    source = _make_source(tmp_path, "a.txt")
    target = tmp_path / "2026-08" / "20260819_a.txt"
    plan = [PlanEntry(source=source, target=target, year_month="2026-08")]
    report_path = tmp_path / "report.md"

    failures, report_error = apply_plan(plan, report_path, tmp_path)

    assert failures == 0
    assert report_error is None
    assert target.exists()
    assert not source.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "完了" in report


def test_apply_plan_continues_after_one_entry_fails(tmp_path):
    # Pre-create a *file* where an entry's target directory should be, so
    # mkdir(parents=True) fails for that entry only.
    blocked_dir = tmp_path / "2026-08"
    blocked_dir.write_text("this is a file, not a directory", encoding="utf-8")

    source_fail = _make_source(tmp_path, "fail.txt")
    source_ok = _make_source(tmp_path, "ok.txt")
    plan = [
        PlanEntry(source=source_fail, target=blocked_dir / "20260819_fail.txt", year_month="2026-08"),
        PlanEntry(source=source_ok, target=tmp_path / "2026-09" / "20260919_ok.txt", year_month="2026-09"),
    ]
    report_path = tmp_path / "report.md"

    failures, report_error = apply_plan(plan, report_path, tmp_path)

    assert failures == 1
    assert report_error is None
    assert source_fail.exists()  # untouched since the move never happened
    assert (tmp_path / "2026-09" / "20260919_ok.txt").exists()
    report = report_path.read_text(encoding="utf-8")
    assert "失敗" in report
    assert "完了" in report


def test_apply_plan_renames_on_collision_drift(tmp_path):
    source = _make_source(tmp_path, "a.txt")
    target_dir = tmp_path / "2026-08"
    target_dir.mkdir()
    target = target_dir / "20260819_a.txt"
    # Simulate a file that appeared at the planned target after the plan was built.
    target.write_text("someone else's file", encoding="utf-8")

    plan = [PlanEntry(source=source, target=target, year_month="2026-08")]
    report_path = tmp_path / "report.md"

    failures, report_error = apply_plan(plan, report_path, tmp_path)

    assert failures == 0
    assert report_error is None
    assert target.read_text(encoding="utf-8") == "someone else's file"
    renamed = target_dir / "20260819_a_2.txt"
    assert renamed.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "衝突のため名称変更" in report


def test_apply_plan_backs_up_foreign_report_instead_of_overwriting(tmp_path):
    source = _make_source(tmp_path, "a.txt")
    target = tmp_path / "2026-08" / "20260819_a.txt"
    plan = [PlanEntry(source=source, target=target, year_month="2026-08")]
    report_path = tmp_path / "report.md"
    report_path.write_text("これはユーザーが作成した無関係なファイルです", encoding="utf-8")

    failures, report_error = apply_plan(plan, report_path, tmp_path)

    assert failures == 0
    assert report_error is None
    assert "完了" in report_path.read_text(encoding="utf-8")
    backup = tmp_path / "report.md.bak"
    assert backup.read_text(encoding="utf-8") == "これはユーザーが作成した無関係なファイルです"


def test_apply_plan_overwrites_report_from_a_previous_run(tmp_path):
    source = _make_source(tmp_path, "a.txt")
    target = tmp_path / "2026-08" / "20260819_a.txt"
    plan = [PlanEntry(source=source, target=target, year_month="2026-08")]
    report_path = tmp_path / "report.md"
    report_path.write_text("# ファイル整理レポート 2026-08-01 00:00\n\n(old report)\n", encoding="utf-8")

    failures, report_error = apply_plan(plan, report_path, tmp_path)

    assert failures == 0
    assert report_error is None
    assert not (tmp_path / "report.md.bak").exists()
    assert "old report" not in report_path.read_text(encoding="utf-8")


def test_apply_plan_rejects_target_that_escapes_base_dir(tmp_path):
    source = _make_source(tmp_path, "a.txt")
    outside = tmp_path / "outside" / "a.txt"
    # Bypass build_plan's own source check to exercise apply_plan's independent
    # move-time containment check directly.
    plan = [PlanEntry(source=source, target=outside, year_month="2026-08")]
    report_path = tmp_path / "base" / "report.md"
    (tmp_path / "base").mkdir()

    failures, report_error = apply_plan(plan, report_path, tmp_path / "base")

    assert failures == 1
    assert report_error is None
    assert source.exists()
    assert not outside.exists()
