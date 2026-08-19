from pathlib import Path

_FALLBACK_ENCODINGS = ("utf-8-sig", "cp932")


def text_to_markdown(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in _FALLBACK_ENCODINGS:
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    # Match the universal-newline normalization that Path.read_text() used to
    # provide, so CRLF-authored files decode the same way regardless of encoding.
    return text.replace("\r\n", "\n").replace("\r", "\n")
