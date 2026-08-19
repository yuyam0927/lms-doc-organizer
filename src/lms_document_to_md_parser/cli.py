import argparse
import sys
from pathlib import Path

from .organize import ManifestError, apply_plan, build_plan, format_preview
from .parsers import SUPPORTED_EXTENSIONS
from .parsers.pdf_parser import UnextractablePdfError


def _iter_input_files(input_path: Path, recursive: bool):
    if input_path.is_file():
        yield input_path
        return
    pattern = "**/*" if recursive else "*"
    for path in sorted(input_path.glob(pattern)):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def convert_file(path: Path, output_dir: Path) -> Path:
    converter = SUPPORTED_EXTENSIONS[path.suffix.lower()]
    markdown = converter(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{path.name}.md"
    out_path.write_text(markdown, encoding="utf-8")
    return out_path


def _run_convert(args: argparse.Namespace) -> int:
    if not args.input.exists():
        print(f"error: input path not found: {args.input}", file=sys.stderr)
        return 1

    exit_code = 0
    for path in _iter_input_files(args.input, args.recursive):
        try:
            out_path = convert_file(path, args.output)
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
        apply_plan(plan, report_path)
        print(f"\nDone. Report written to {report_path}")
    else:
        print("\n(dry run -- re-run with --apply to execute)")

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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
