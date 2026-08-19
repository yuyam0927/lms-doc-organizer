# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                                          # install runtime + dev (pytest) dependencies
uv run pytest                                    # run the full test suite
uv run pytest tests/test_organize.py             # run one test file
uv run pytest tests/test_organize.py::test_build_plan_rejects_malformed_date  # run a single test
uv run lms-doc2md convert path/to/file.docx -o out/       # convert one file
uv run lms-doc2md convert path/to/dir -o out/ --recursive # convert a directory tree
uv run lms-doc2md organize manifest.json --base-dir path/to/dir           # dry run
uv run lms-doc2md organize manifest.json --base-dir path/to/dir --apply   # actually move/rename
```

There is no lint/format/typecheck tooling configured in this repo (no ruff/mypy config). `uv sync` creates
`.venv/`; `uv run` uses it automatically.

## Architecture

This is a CLI (`lms-doc2md`, entry point `lms_document_to_md_parser.cli:main`) with two independent
subcommands that are designed to be chained together by an LLM agent (see "LM Studio Skill" below), not
typically by a human running both by hand.

**`convert`** (`cli.py` + `parsers/`): turns `.docx`/`.pdf`/`.xlsx`/`.txt`/`.md` into Markdown.
`parsers/__init__.py` maps file extensions to parser functions via `SUPPORTED_EXTENSIONS`; `cli.py` looks
up the converter purely by extension. Each parser module (`docx_parser.py`, `pdf_parser.py`,
`xlsx_parser.py`, `text_parser.py`) exposes a single `*_to_markdown(path: Path) -> str` function with no
shared base class — to add a format, write a new `_to_markdown` function and register it in
`SUPPORTED_EXTENSIONS`. All three table-producing parsers (docx/pdf/xlsx) render tables through the shared
`parsers/_markdown.py::rows_to_table()`, which escapes `|`/newlines/backslashes per cell — always route new
table output through this helper rather than hand-building `| ... |` strings, or generated Markdown tables
silently break on real-world cell content.

`pdf_parser.py` is the most involved parser: it merges body text and tables in the same top-to-bottom
order they appear in the source PDF (not "all text, then all tables"), by pulling `extract_text_lines()`
and `find_tables()` from pdfplumber, filtering table-region characters out of the text via
`page.filter()`/`_table_bbox_filter()`, and interleaving the two by vertical position (`_extract_page_blocks`).
pdfplumber represents empty table cells as `None`, not `""` — `_normalize_table_rows()` handles that before
cells reach `rows_to_table()`. A page with no extractable text/tables gets a visible placeholder block
instead of being silently dropped; `UnextractablePdfError` is only raised when *no* page in the document
had any content (e.g. a fully scanned-image PDF), letting `cli.py` report it as a per-file `SKIP`.
`xlsx_parser.py` reads the workbook twice (`data_only=True` and `data_only=False`) so formula cells without
a cached value fall back to showing the formula text instead of vanishing.

**`organize`** (`organize.py`): takes a JSON manifest (`[{source, title, date?}, ...]`, normally produced
by an LLM after reading the converted Markdown) and moves the *original* source files into
`<base-dir>/YYYY-MM/YYYYMMDD_title.ext`. `build_plan()` validates the manifest and computes a `PlanEntry`
list without touching the filesystem (used for both the dry-run preview and as the first half of `--apply`);
`apply_plan()` does the actual `shutil.move` + writes a `report.md`. Two things worth knowing before editing
this file:
- `build_plan()` rejects any manifest `source` that resolves outside `base_dir` — this is a deliberate
  guard against a manifest (which may have been populated by an LLM after reading untrusted document
  content) being tricked into moving arbitrary files.
- `apply_plan()` re-derives collision-free target paths and re-checks the `base_dir` containment right
  before each move, because the plan is normally built once for the dry-run preview and then rebuilt in a
  *separate* CLI invocation for `--apply` — the filesystem can have changed in between.

**LM Studio Skill** (`skills/organize-documents/SKILL.md`): a prompt-driven runbook, not code, that an LLM
agent inside LM Studio follows to chain `convert` → read the Markdown → decide title/date → write a
manifest → `organize` (preview, then `--apply` after user confirmation). It assumes the agent has
`run_command`/`read_file`/`write_file` tools from an LM Studio "skills" plugin (e.g. imezx/skills) — not
from LM Studio's official filesystem MCP server, which typically lacks `run_command`. When editing this
file, keep in mind the model reading it may be a small local model, so steps are meant to be followed
literally in order rather than inferred.

## Testing conventions

`pdf_parser.py` is tested against fakes (`FakePage`/`FakeTable` in `tests/test_pdf_parser.py`) rather than
real PDF fixtures, since there's no PDF-writing dependency in this project. The fakes intentionally mirror
pdfplumber's actual API shape (`find_tables()`, `filter(predicate)`, `extract_text_lines()` returning
dicts with `top`/`text`/`x0`/`x1`/`bottom`) closely enough that `filter()` really applies the predicate —
don't simplify it back to a no-op, or table/text de-duplication stops being tested. `tests/test_cli.py`
and `tests/test_organize.py` drive real files under `tmp_path` rather than mocking the filesystem.
