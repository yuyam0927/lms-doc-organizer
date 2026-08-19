# lms-document-to-md-parser

`docx` / `pdf` / `xlsx` / `txt` / `md` ファイルを Markdown に変換する CLI ツール。
LM Studio の Skill 機能から呼び出し、ローカルLLMにドキュメントの内容を読ませるための前処理として利用する想定。

## 使い方(uvx / インストール不要)

```bash
# GitHub リポジトリから直接実行
uvx --from git+https://github.com/yuyam0927/lms-document-to-md-parser lms-doc2md path/to/file.docx -o out/

# ディレクトリを一括変換
uvx --from git+https://github.com/yuyam0927/lms-document-to-md-parser lms-doc2md path/to/dir -o out/ --recursive
```

## ローカル開発

```bash
uv sync
uv run lms-doc2md sample.docx -o out/
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
