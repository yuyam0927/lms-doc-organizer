# Organize Documents Skill

Renames docx / pdf / xlsx / txt / md files in a given folder based on their content
(a short title and a date), and moves them into `YYYY-MM` subfolders.

Note: the files you process will contain Japanese text. This is expected — read
titles and dates in Japanese, but write them into the manifest as plain strings.

Follow these steps in exact order. Do not skip steps or combine them.
The only two things you need to judge are: "what is a short title for this document"
and "does the text contain an explicit date". Everything else is a fixed command —
run it exactly as written.

## Steps

### 0. Confirm the target folder

Read the target folder path from the user's request.
If the path is not clear, STOP and ask the user for the folder (require an absolute path).
Do not guess a default folder.

Below, the target folder is written as `<TARGET>`.

### 1. Convert all files to Markdown

Run with `run_command` (add `--recursive` only if the user asked to include subfolders;
otherwise omit it):

```
uvx --from git+https://github.com/yuyam0927/lms-document-to-md-parser lms-doc2md convert "<TARGET>" -o "<TARGET>\.lms-doc2md-tmp"
```

- Lines starting with `OK` converted successfully.
- Lines starting with `SKIP` (usually scanned image PDFs with no extractable text) are
  excluded from this run. Do not stop — continue to the next step, and mention these
  files in the final report.
- Lines starting with `ERROR` are also excluded. Continue, and mention them in the
  final report.

### 2. Read each file and decide a title and a date

For every `*.md` file inside `<TARGET>\.lms-doc2md-tmp`, read it one at a time with
`read_file` (the first ~3000 characters is enough if the file is long).

For each file, decide exactly two things:

- **title**: a short title in Japanese (about 20 characters or less) describing the
  document, based on the filename, headings, or the opening sentence. Do not use the
  characters `/` `\` `:` `*` `?` `"` `<` `>` `|`.
- **date**: only if the document text explicitly states a date, extract it in
  `YYYY-MM-DD` format (example: "2026年8月19日" → `2026-08-19`). If no explicit date is
  found, **omit the `date` field entirely**. Never guess a date.

### 3. Write the manifest

Write the decisions from step 2 as a JSON array using `write_file`, saved to
`<TARGET>\.lms-doc2md-tmp\manifest.json`.

`source` must be the path to the **original file** (the docx/pdf/xlsx/txt/md file,
not the `.md` conversion output). Do not include files that were `SKIP` or `ERROR`
in step 1.

```json
[
  { "source": "<TARGET>\\report.docx", "title": "第3四半期売上報告", "date": "2026-08-19" },
  { "source": "<TARGET>\\memo.txt", "title": "会議メモ" }
]
```

### 4. Run a dry-run preview

Run with `run_command` (do NOT add `--apply`):

```
uvx --from git+https://github.com/yuyam0927/lms-document-to-md-parser lms-doc2md organize "<TARGET>\.lms-doc2md-tmp\manifest.json" --base-dir "<TARGET>"
```

Show the resulting Markdown table to the user exactly as printed, and ask:
"Should I go ahead and rename/move these files?"
**Do not proceed to the next step until the user clearly approves.**

### 5. Apply

Once the user approves, run with `run_command` (add `--apply`):

```
uvx --from git+https://github.com/yuyam0927/lms-document-to-md-parser lms-doc2md organize "<TARGET>\.lms-doc2md-tmp\manifest.json" --base-dir "<TARGET>" --apply
```

This writes a report to `<TARGET>\report.md` and actually renames/moves the files.

If the user does not approve, stop here — do not run step 6.

### 6. Clean up and report

Remove the temporary folder with `run_command`:

```
rmdir /s /q "<TARGET>\.lms-doc2md-tmp"
```

Finally, report the following to the user:

- Number of files renamed/moved
- Any files excluded (SKIP / ERROR) and why
- The report location (`<TARGET>\report.md`)
