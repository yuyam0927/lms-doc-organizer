# lms-doc-organizer

> このプロジェクトは [Claude](https://claude.com/claude-code)(Anthropic)と
> [Codex](https://openai.com/codex/)(OpenAI)によって作成されています。

`docx` / `pdf` / `xlsx` / `txt` / `md` ファイルを Markdown に変換する CLI ツール。
変換したMarkdownをローカルLLM(LM Studio)にタイトル判定だけさせ、ファイルの整理・リネームまで行う
`auto-organize` コマンドも提供しています。

## 使い方(uvx / インストール不要)

```bash
# GitHub リポジトリから直接実行(1ファイル変換)
uvx --from git+https://github.com/yuyam0927/lms-doc-organizer lms-doc2md convert path/to/file.docx -o out/

# ディレクトリを一括変換
uvx --from git+https://github.com/yuyam0927/lms-doc-organizer lms-doc2md convert path/to/dir -o out/ --recursive
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
uvx --from git+https://github.com/yuyam0927/lms-doc-organizer lms-doc2md organize manifest.json --base-dir path/to/dir

# 実行(実際に移動・リネームし、<base-dir>/report.md にレポートを出力)
uvx --from git+https://github.com/yuyam0927/lms-doc-organizer lms-doc2md organize manifest.json --base-dir path/to/dir --apply
```

### 自動整理(auto-organize)

`convert` → LM Studioのローカルモデルにタイトル(・日付)を判定させる → 一覧プレビュー →
ユーザー確認 → `organize --apply` までを1コマンドで実行します。LLMの役割はタイトル判定
だけに絞られており、ファイル走査・変換・確認・リネームは全てこのコマンド(Python側)が行います。

事前に LM Studio を起動し、モデルをロードしてローカルサーバー(既定 `http://localhost:1234/v1`)
を有効にしておいてください。

```bash
# 対象フォルダ内のプレビューを表示し、確認後に実行
uvx --from git+https://github.com/yuyam0927/lms-doc-organizer lms-doc2md auto-organize path/to/dir

# サブフォルダも対象にする / 確認プロンプトを省略する
uvx --from git+https://github.com/yuyam0927/lms-doc-organizer lms-doc2md auto-organize path/to/dir --recursive --yes

# 使用モデル・APIエンドポイントを明示指定
uvx --from git+https://github.com/yuyam0927/lms-doc-organizer lms-doc2md auto-organize path/to/dir --llm-model qwen2.5-7b-instruct --llm-base-url http://localhost:1234/v1
```

タイトル/日付の判定に失敗したファイル(LM Studioに接続できない、モデルが不正なJSONを返す等)は
その1件だけスキップされ、他のファイルの処理は続行されます。

文書内の日付が「令和8年6月8日」のような和暦表記でも、西暦への変換はPython側で行うため
(LLMには変換させない)、正しく `2026-06-08` として認識されます。

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
