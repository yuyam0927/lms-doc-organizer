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
`YYYY-MM_タイトル` 形式にリネームして `<base-dir>/YYYY-MM/` フォルダへ移動します。
`date` を省略した場合はファイルの更新日時が使われます。

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
