from lms_document_to_md_parser.parsers.text_parser import text_to_markdown


def test_text_to_markdown_reads_utf8(tmp_path):
    path = tmp_path / "memo.txt"
    path.write_text("日本語のメモ\n2行目", encoding="utf-8")

    assert text_to_markdown(path) == "日本語のメモ\n2行目"


def test_text_to_markdown_replaces_invalid_bytes(tmp_path):
    path = tmp_path / "broken.txt"
    path.write_bytes(b"valid \xff\xfe invalid")

    result = text_to_markdown(path)

    assert "valid" in result
    assert "invalid" in result


def test_text_to_markdown_falls_back_to_cp932(tmp_path):
    path = tmp_path / "sjis.txt"
    path.write_bytes("日本語のメモ".encode("cp932"))

    assert text_to_markdown(path) == "日本語のメモ"


def test_text_to_markdown_strips_utf8_bom(tmp_path):
    path = tmp_path / "bom.txt"
    path.write_bytes("こんにちは".encode("utf-8-sig"))

    assert text_to_markdown(path) == "こんにちは"
