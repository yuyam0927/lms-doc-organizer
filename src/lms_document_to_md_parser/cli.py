import argparse
import json
import sys
import tempfile
from pathlib import Path

from .llm_client import DEFAULT_BASE_URL, LlmError, resolve_model, suggest_title
from .organize import ManifestError, apply_plan, build_plan, format_preview
from .parsers import SUPPORTED_EXTENSIONS
from .parsers.pdf_parser import UnextractablePdfError


def _iter_input_files(input_path: Path, recursive: bool, exclude: Path | None = None):
    if input_path.is_file():
        yield input_path
        return
    pattern = "**/*" if recursive else "*"
    for path in sorted(input_path.glob(pattern)):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if exclude is not None:
            resolved = path.resolve()
            if resolved == exclude or exclude in resolved.parents:
                continue
        yield path


def convert_file(path: Path, output_dir: Path, *, root: Path | None = None) -> Path:
    converter = SUPPORTED_EXTENSIONS[path.suffix.lower()]
    markdown = converter(path)

    if root is not None:
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = Path(path.name)
    else:
        relative = Path(path.name)

    out_path = output_dir / relative.parent / f"{relative.name}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    return out_path


def _run_convert(args: argparse.Namespace) -> int:
    if not args.input.exists():
        print(f"error: input path not found: {args.input}", file=sys.stderr)
        return 1

    root = args.input if args.input.is_dir() else None
    output_resolved = args.output.resolve()
    exit_code = 0
    for path in _iter_input_files(args.input, args.recursive, exclude=output_resolved):
        try:
            out_path = convert_file(path, args.output, root=root)
            print(f"OK    {path} -> {out_path}")
        except UnextractablePdfError as exc:
            print(f"SKIP  {exc}", file=sys.stderr)
            exit_code = 1
        except Exception as exc:  # noqa: BLE001 - surface conversion errors per file
            print(f"ERROR {path}: {exc}", file=sys.stderr)
            exit_code = 1

    return exit_code


def _run_organize(args: argparse.Namespace) -> int:
    if not args.manifest.exists():
        print(f"error: manifest not found: {args.manifest}", file=sys.stderr)
        return 1

    try:
        plan = build_plan(args.manifest, args.base_dir)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not plan:
        print("no entries in manifest")
        return 0

    print(format_preview(plan))

    if args.apply:
        report_path = args.base_dir / "report.md"
        failures, report_error = apply_plan(plan, report_path, args.base_dir)
        succeeded = len(plan) - failures
        if report_error:
            print(
                f"error: {succeeded}/{len(plan)} files were moved, but the report could not be "
                f"written to {report_path}: {report_error}",
                file=sys.stderr,
            )
            return 1
        print(f"\nDone ({succeeded}/{len(plan)} succeeded). Report written to {report_path}")
        if failures:
            print(f"warning: {failures} entr{'y' if failures == 1 else 'ies'} failed to move", file=sys.stderr)
            return 1
    else:
        print("\n(dry run -- re-run with --apply to execute)")

    return 0


def _run_auto_organize(args: argparse.Namespace) -> int:
    if not args.target.exists():
        print(f"error: target path not found: {args.target}", file=sys.stderr)
        return 1
    if not args.target.is_dir():
        print(f"error: target must be a directory: {args.target}", file=sys.stderr)
        return 1

    base_dir = args.base_dir if args.base_dir is not None else args.target

    try:
        model = args.llm_model or resolve_model(args.llm_base_url, args.llm_timeout)
    except LlmError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    manifest_entries = []
    skipped = 0

    with tempfile.TemporaryDirectory(prefix="lms-doc2md-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        for path in _iter_input_files(args.target, args.recursive):
            try:
                markdown = SUPPORTED_EXTENSIONS[path.suffix.lower()](path)
            except UnextractablePdfError as exc:
                print(f"SKIP  {exc}", file=sys.stderr)
                skipped += 1
                continue
            except Exception as exc:  # noqa: BLE001 - surface conversion errors per file
                print(f"ERROR {path}: {exc}", file=sys.stderr)
                skipped += 1
                continue

            try:
                suggestion = suggest_title(
                    markdown, base_url=args.llm_base_url, model=model, timeout=args.llm_timeout
                )
            except LlmError as exc:
                print(f"ERROR {path}: title suggestion failed: {exc}", file=sys.stderr)
                skipped += 1
                continue

            entry = {"source": str(path), "title": suggestion["title"]}
            if suggestion.get("date"):
                entry["date"] = suggestion["date"]
            manifest_entries.append(entry)
            print(f"OK    {path} -> title={entry['title']!r} date={entry.get('date')!r}")

        if not manifest_entries:
            print("no files to organize")
            return 1 if skipped else 0

        manifest_path = tmp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_entries, ensure_ascii=False), encoding="utf-8")

        try:
            plan = build_plan(manifest_path, base_dir)
        except ManifestError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        print()
        print(format_preview(plan))

        if not args.yes:
            answer = input("\n上記の内容でファイルを移動/リネームしますか? [y/N]: ").strip().lower()
            if answer not in ("y", "yes"):
                print("キャンセルしました。")
                return 0

        report_path = base_dir / "report.md"
        failures, report_error = apply_plan(plan, report_path, base_dir)
        succeeded = len(plan) - failures
        if report_error:
            print(
                f"error: {succeeded}/{len(plan)} files were moved, but the report could not be "
                f"written to {report_path}: {report_error}",
                file=sys.stderr,
            )
            return 1
        print(f"\nDone ({succeeded}/{len(plan)} succeeded). Report written to {report_path}")
        if failures:
            print(f"warning: {failures} entr{'y' if failures == 1 else 'ies'} failed to move", file=sys.stderr)
            return 1

    if skipped:
        print(f"\n{skipped} file(s) skipped due to errors (see above)", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="lms-doc2md",
        description="Convert documents to Markdown, and organize files into dated folders.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert_parser = subparsers.add_parser("convert", help="Convert docx/pdf/xlsx/txt/md files into Markdown")
    convert_parser.add_argument("input", type=Path, help="File or directory to convert")
    convert_parser.add_argument(
        "-o", "--output", type=Path, default=Path("."), help="Output directory (default: current directory)"
    )
    convert_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recurse into subdirectories when input is a directory"
    )
    convert_parser.set_defaults(func=_run_convert)

    organize_parser = subparsers.add_parser(
        "organize", help="Rename and move files into YYYY-MM folders based on a manifest"
    )
    organize_parser.add_argument("manifest", type=Path, help="JSON manifest: [{source, title, date?}, ...]")
    organize_parser.add_argument(
        "--base-dir", type=Path, required=True, help="Directory under which YYYY-MM folders are created"
    )
    organize_parser.add_argument(
        "--apply", action="store_true", help="Actually move/rename files (default is dry run preview only)"
    )
    organize_parser.set_defaults(func=_run_organize)

    auto_parser = subparsers.add_parser(
        "auto-organize",
        help="Convert, ask a local LM Studio model for titles, and organize files in one command",
    )
    auto_parser.add_argument("target", type=Path, help="Folder containing files to organize")
    auto_parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Directory under which YYYY-MM folders are created (default: target)",
    )
    auto_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recurse into subdirectories"
    )
    auto_parser.add_argument(
        "--llm-base-url",
        default=DEFAULT_BASE_URL,
        help=f"LM Studio OpenAI-compatible API base URL (default: {DEFAULT_BASE_URL})",
    )
    auto_parser.add_argument(
        "--llm-model", default=None, help="Model id to use (default: first loaded model in LM Studio)"
    )
    auto_parser.add_argument(
        "--llm-timeout", type=float, default=60.0, help="Per-request timeout in seconds (default: 60)"
    )
    auto_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip the confirmation prompt and apply immediately"
    )
    auto_parser.set_defaults(func=_run_auto_organize)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
