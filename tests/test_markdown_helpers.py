from lms_document_to_md_parser.parsers._markdown import escape_cell, rows_to_table


def test_escape_cell_escapes_pipe_and_backslash():
    assert escape_cell("a|b") == "a\\|b"
    assert escape_cell("a\\b") == "a\\\\b"


def test_escape_cell_converts_newline_to_br():
    assert escape_cell("line1\nline2") == "line1<br>line2"


def test_escape_cell_plain_text_unchanged():
    assert escape_cell("plain") == "plain"


def test_rows_to_table_empty_returns_empty_string():
    assert rows_to_table([]) == ""


def test_rows_to_table_renders_header_and_body():
    md = rows_to_table([["h1", "h2"], ["a", "b"]])
    assert md == "| h1 | h2 |\n| --- | --- |\n| a | b |"


def test_rows_to_table_escapes_cells():
    md = rows_to_table([["h1", "h2"], ["a|b", "line1\nline2"]])
    lines = md.splitlines()
    assert lines[2] == "| a\\|b | line1<br>line2 |"
