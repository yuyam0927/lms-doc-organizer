import argparse
import sys
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lms-doc2md",
        description="Convert docx, pdf, xlsx, txt, and md files into Markdown.",
    )
    parser.add_argument("input", type=Path, help="File or directory to convert")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("."), help="Output directory (default: current directory)"
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recurse into subdirectories when input is a directory"
    )
    args = parser.parse_args(argv)

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


if __name__ == "__main__":
    raise SystemExit(main())
