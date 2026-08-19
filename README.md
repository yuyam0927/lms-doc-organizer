# lms-document-to-md-parser

`docx` / `pdf` / `xlsx` / `txt` / `md` ファイルを Markdown に変換する CLI ツール。
LM Studio の Skill 機能から呼び出し、ローカルLLMにドキュメントの内容を読ませるための前処理として利用する想定。

## 使い方(uvx / インストール不要)

```bash
# GitHub リポジトリから直接実行(1ファイル変換)
uvx --from git+https://github.com/yuyam0927/lms-document-to-md-parser lms-doc2md convert path/to/file.docx -o out/

# ディレクトリを一括変換
uvx --from git+https://github.com/yuyam0927/lms-document-to-md-parser lms-doc2md convert path/to/dir -o out/ --recursive
```

### ファイルの命名・整理(organize)

`title`(・任意で `date`)を指定した JSON マニフェストをもとに、ファイルを
`YYYYMMDD_タイトル` 形式にリネームして `<base-dir>/YYYY-MM/` フォルダへ移動します。
`date` を省略した場合はファイルの更新日時が使われます(指定する場合は `YYYY-MM-DD` 形式のみ有効)。
`source` に指定できるのは `--base-dir` 配下のファイルのみです。

```bash
# manifest.json:
# [{"source": "path/to/report.docx", "title": "第3四半期売上報告", "date": "2026-08-19"}]

# ドライラン(プレビューのみ、何も変更されない)
uvx --from git+https://github.com/yuyam0927/lms-document-to-md-parser lms-doc2md organize manifest.json --base-dir path/to/dir

# 実行(実際に移動・リネームし、<base-dir>/report.md にレポートを出力)
uvx --from git+https://github.com/yuyam0927/lms-document-to-md-parser lms-doc2md organize manifest.json --base-dir path/to/dir --apply
```

## LM Studio Skill として使う

[`skills/organize-documents/`](skills/organize-documents/) を
`~/.lmstudio/skills/organize-documents/` にコピーすると、LM Studio 上で
「`<フォルダパス>` を整理して」と指示するだけで、`convert` → タイトル・日付判定 →
プレビュー確認 → `organize --apply` → レポート出力、までを自動実行できます。
手順の詳細は [SKILL.md](skills/organize-documents/SKILL.md) を参照してください。

**前提条件**: この SKILL.md はモデルが `run_command`(シェルコマンド実行)・
`read_file`・`write_file` という名前のツールを使える前提で書かれています。これらは
LM Studio 公式の filesystem MCP サーバー(通常 `run_command` は含まれません)ではなく、
Claude の Skill 機能を LM Studio に移植した [imezx/skills](https://github.com/imezx/skills)
系のプラグイン(`read_file`/`write_file`/`run_command` を含む一式のツールをネイティブに
提供する LM Studio プラグイン)を想定しています。このプラグインを導入していれば、
filesystem MCP サーバーは別途接続しなくても動作します。異なるツール名を提供する環境
(例: filesystem MCP のみで `run_command` 相当が無い環境)では、SKILL.md 内のツール名を
実際の環境に合わせて読み替えるか、シェル実行が可能な別のツール/MCPサーバーを追加導入
してください。

## ローカル開発

```bash
uv sync
uv run lms-doc2md convert sample.docx -o out/
```

## 対応形式

| 拡張子 | 変換内容 |
|---|---|
| `.docx` | 見出し・段落・表を Markdown 化 |
| `.pdf` | ページ単位でテキスト・表を抽出(スキャン画像PDFはOCR非対応のためスキップ) |
| `.xlsx` | シートごとに Markdown テーブル化 |
| `.txt` / `.md` | そのまま読み込み |

## 制限事項

- 画像ファイルは対象外
- テキスト抽出できないスキャンPDF(OCR非対応)は変換をスキップし、エラーとして報告
- docxの番号付きリスト(`List Number`等)は箇条書き(`-`)として出力され、元の番号は再現されません
- `.xlsx`で数式セルにキャッシュ済みの計算結果が無い場合(Excel等で一度も開かれていないファイル等)は、値の代わりに数式文字列(例: `=SUM(A1:A2)`)がそのまま出力されます
