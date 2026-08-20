import json
from pathlib import Path

import lms_document_to_md_parser.cli as cli_module
from lms_document_to_md_parser.cli import _iter_input_files, convert_file, main
from lms_document_to_md_parser.llm_client import LlmError


# ---- convert_file / _iter_input_files --------------------------------------


def test_convert_file_flattens_when_no_root(tmp_path):
    src_dir = tmp_path / "in"
    src_dir.mkdir()
    (src_dir / "a.txt").write_text("hello", encoding="utf-8")
    out_dir = tmp_path / "out"

    out_path = convert_file(src_dir / "a.txt", out_dir)

    assert out_path == out_dir / "a.txt.md"
    assert out_path.read_text(encoding="utf-8") == "hello"


def test_convert_file_preserves_relative_dirs_to_avoid_collisions(tmp_path):
    src_dir = tmp_path / "in"
    (src_dir / "sub").mkdir(parents=True)
    (src_dir / "report.txt").write_text("top", encoding="utf-8")
    (src_dir / "sub" / "report.txt").write_text("nested", encoding="utf-8")
    out_dir = tmp_path / "out"

    top_out = convert_file(src_dir / "report.txt", out_dir, root=src_dir)
    nested_out = convert_file(src_dir / "sub" / "report.txt", out_dir, root=src_dir)

    assert top_out != nested_out
    assert top_out == out_dir / "report.txt.md"
    assert nested_out == out_dir / "sub" / "report.txt.md"
    assert top_out.read_text(encoding="utf-8") == "top"
    assert nested_out.read_text(encoding="utf-8") == "nested"


def test_iter_input_files_non_recursive_skips_subdirs(tmp_path):
    (tmp_path / "top.txt").write_text("x", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_text("x", encoding="utf-8")

    files = sorted(p.name for p in _iter_input_files(tmp_path, recursive=False))

    assert files == ["top.txt"]


def test_iter_input_files_recursive_includes_subdirs(tmp_path):
    (tmp_path / "top.txt").write_text("x", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_text("x", encoding="utf-8")

    files = sorted(p.name for p in _iter_input_files(tmp_path, recursive=True))

    assert files == ["nested.txt", "top.txt"]


def test_iter_input_files_ignores_unsupported_extensions(tmp_path):
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
    (tmp_path / "skip.bin").write_bytes(b"\x00\x01")

    files = sorted(p.name for p in _iter_input_files(tmp_path, recursive=False))

    assert files == ["keep.txt"]


# ---- main(): convert subcommand --------------------------------------------


def test_main_convert_reports_missing_input(capsys, tmp_path):
    exit_code = main(["convert", str(tmp_path / "missing"), "-o", str(tmp_path / "out")])

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


def test_main_convert_succeeds_and_writes_markdown(capsys, tmp_path):
    src_dir = tmp_path / "in"
    src_dir.mkdir()
    (src_dir / "memo.txt").write_text("こんにちは", encoding="utf-8")
    out_dir = tmp_path / "out"

    exit_code = main(["convert", str(src_dir), "-o", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / "memo.txt.md").read_text(encoding="utf-8") == "こんにちは"
    assert "OK" in capsys.readouterr().out


def test_main_convert_recursive_avoids_overwriting_same_named_files(tmp_path):
    src_dir = tmp_path / "in"
    (src_dir / "sub").mkdir(parents=True)
    (src_dir / "report.txt").write_text("top", encoding="utf-8")
    (src_dir / "sub" / "report.txt").write_text("nested", encoding="utf-8")
    out_dir = tmp_path / "out"

    exit_code = main(["convert", str(src_dir), "-o", str(out_dir), "--recursive"])

    assert exit_code == 0
    assert (out_dir / "report.txt.md").read_text(encoding="utf-8") == "top"
    assert (out_dir / "sub" / "report.txt.md").read_text(encoding="utf-8") == "nested"


# ---- main(): organize subcommand -------------------------------------------


def test_main_organize_reports_missing_manifest(capsys, tmp_path):
    exit_code = main(["organize", str(tmp_path / "missing.json"), "--base-dir", str(tmp_path)])

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


def test_main_organize_dry_run_does_not_move_files(capsys, tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("x", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps([{"source": str(source), "title": "レポート", "date": "2026-08-19"}]),
        encoding="utf-8",
    )

    exit_code = main(["organize", str(manifest), "--base-dir", str(tmp_path)])

    assert exit_code == 0
    assert source.exists()
    assert not (tmp_path / "2026-08").exists()
    out = capsys.readouterr().out
    assert "dry run" in out


def test_main_organize_apply_moves_files_and_writes_report(tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("x", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps([{"source": str(source), "title": "レポート", "date": "2026-08-19"}]),
        encoding="utf-8",
    )

    exit_code = main(["organize", str(manifest), "--base-dir", str(tmp_path), "--apply"])

    assert exit_code == 0
    assert not source.exists()
    assert (tmp_path / "2026-08" / "20260819_レポート.txt").exists()
    assert (tmp_path / "report.md").exists()


def test_main_organize_apply_returns_nonzero_on_partial_failure(capsys, tmp_path):
    # Block one entry's target directory with a same-named file.
    (tmp_path / "2026-08").write_text("blocking file", encoding="utf-8")

    source = tmp_path / "report.txt"
    source.write_text("x", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps([{"source": str(source), "title": "レポート", "date": "2026-08-19"}]),
        encoding="utf-8",
    )

    exit_code = main(["organize", str(manifest), "--base-dir", str(tmp_path), "--apply"])

    assert exit_code == 1
    assert "failed to move" in capsys.readouterr().err


def test_main_organize_rejects_source_outside_base_dir(capsys, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    source = outside / "secret.txt"
    source.write_text("x", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps([{"source": str(source), "title": "外部"}]), encoding="utf-8"
    )

    exit_code = main(["organize", str(manifest), "--base-dir", str(base_dir)])

    assert exit_code == 1
    assert source.exists()


# ---- main(): auto-organize subcommand ---------------------------------------


def _stub_suggest_title(markdown, *, base_url, model, timeout):
    return {"title": f"タイトル_{markdown}", "date": "2026-08-19"}


def test_main_auto_organize_reports_missing_target(capsys, tmp_path):
    exit_code = main(["auto-organize", str(tmp_path / "missing")])

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


def test_main_auto_organize_reports_llm_connection_failure(monkeypatch, capsys, tmp_path):
    def fake_resolve_model(base_url, timeout):
        raise LlmError("boom")

    monkeypatch.setattr(cli_module, "resolve_model", fake_resolve_model)

    exit_code = main(["auto-organize", str(tmp_path)])

    assert exit_code == 1
    assert "boom" in capsys.readouterr().err


def test_main_auto_organize_yes_applies_without_prompt(monkeypatch, tmp_path):
    (tmp_path / "memo.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setattr(cli_module, "suggest_title", _stub_suggest_title)

    exit_code = main(["auto-organize", str(tmp_path), "--llm-model", "m", "--yes"])

    assert exit_code == 0
    assert not (tmp_path / "memo.txt").exists()
    assert (tmp_path / "2026-08" / "20260819_タイトル_hello.txt").exists()
    assert (tmp_path / "report.md").exists()


def test_main_auto_organize_without_yes_requires_confirmation(monkeypatch, tmp_path):
    (tmp_path / "memo.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setattr(cli_module, "suggest_title", _stub_suggest_title)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    exit_code = main(["auto-organize", str(tmp_path), "--llm-model", "m"])

    assert exit_code == 0
    assert (tmp_path / "memo.txt").exists()
    assert not (tmp_path / "2026-08").exists()


def test_main_auto_organize_confirmation_yes_applies(monkeypatch, tmp_path):
    (tmp_path / "memo.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setattr(cli_module, "suggest_title", _stub_suggest_title)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    exit_code = main(["auto-organize", str(tmp_path), "--llm-model", "m"])

    assert exit_code == 0
    assert not (tmp_path / "memo.txt").exists()
    assert (tmp_path / "2026-08" / "20260819_タイトル_hello.txt").exists()


def test_main_auto_organize_skips_file_on_title_suggestion_failure(monkeypatch, capsys, tmp_path):
    (tmp_path / "memo.txt").write_text("hello", encoding="utf-8")

    def failing_suggest_title(markdown, *, base_url, model, timeout):
        raise LlmError("model refused")

    monkeypatch.setattr(cli_module, "suggest_title", failing_suggest_title)

    exit_code = main(["auto-organize", str(tmp_path), "--llm-model", "m", "--yes"])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "model refused" in err
    assert (tmp_path / "memo.txt").exists()


def test_main_auto_organize_uses_explicit_base_dir(monkeypatch, tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "memo.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setattr(cli_module, "suggest_title", _stub_suggest_title)

    exit_code = main(
        ["auto-organize", str(src_dir), "--base-dir", str(src_dir), "--llm-model", "m", "--yes"]
    )

    assert exit_code == 0
    assert (src_dir / "2026-08" / "20260819_タイトル_hello.txt").exists()
