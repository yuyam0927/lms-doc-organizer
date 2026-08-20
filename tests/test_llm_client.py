import json
import urllib.error

import pytest

from lms_document_to_md_parser.llm_client import LlmError, resolve_model, suggest_title


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _chat_payload(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


# ---- resolve_model ---------------------------------------------------------


def test_resolve_model_returns_first_loaded_model(monkeypatch):
    def fake_urlopen(req, timeout):
        assert req.full_url == "http://localhost:1234/v1/models"
        return _FakeResponse({"data": [{"id": "model-a"}, {"id": "model-b"}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert resolve_model("http://localhost:1234/v1", 10) == "model-a"


def test_resolve_model_raises_when_no_models_loaded(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _FakeResponse({"data": []}))

    with pytest.raises(LlmError):
        resolve_model("http://localhost:1234/v1", 10)


def test_resolve_model_wraps_connection_errors(monkeypatch):
    def fake_urlopen(req, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(LlmError):
        resolve_model("http://localhost:1234/v1", 10)


def test_resolve_model_wraps_invalid_json(monkeypatch):
    class _BadResponse(_FakeResponse):
        def read(self):
            return b"not json"

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _BadResponse({}))

    with pytest.raises(LlmError):
        resolve_model("http://localhost:1234/v1", 10)


# ---- suggest_title ----------------------------------------------------------


def test_suggest_title_parses_plain_json_response(monkeypatch):
    payload = _chat_payload('{"title": "会議メモ", "date": "2026-08-19"}')
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _FakeResponse(payload))

    result = suggest_title("本文", base_url="http://localhost:1234/v1", model="m", timeout=10)

    assert result == {"title": "会議メモ", "date": "2026-08-19"}


def test_suggest_title_strips_code_fence(monkeypatch):
    payload = _chat_payload('```json\n{"title": "資料", "date": null}\n```')
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _FakeResponse(payload))

    result = suggest_title("本文", base_url="http://localhost:1234/v1", model="m", timeout=10)

    assert result == {"title": "資料", "date": None}


def test_suggest_title_omits_date_when_absent(monkeypatch):
    payload = _chat_payload('{"title": "資料"}')
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _FakeResponse(payload))

    result = suggest_title("本文", base_url="http://localhost:1234/v1", model="m", timeout=10)

    assert result == {"title": "資料", "date": None}


def test_suggest_title_raises_on_missing_title(monkeypatch):
    payload = _chat_payload('{"date": "2026-08-19"}')
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _FakeResponse(payload))

    with pytest.raises(LlmError):
        suggest_title("本文", base_url="http://localhost:1234/v1", model="m", timeout=10)


def test_suggest_title_raises_on_non_json_content(monkeypatch):
    payload = _chat_payload("sorry, I can't help with that")
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _FakeResponse(payload))

    with pytest.raises(LlmError):
        suggest_title("本文", base_url="http://localhost:1234/v1", model="m", timeout=10)


def test_suggest_title_raises_on_malformed_response_shape(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _FakeResponse({"choices": []}))

    with pytest.raises(LlmError):
        suggest_title("本文", base_url="http://localhost:1234/v1", model="m", timeout=10)


def test_suggest_title_wraps_connection_errors(monkeypatch):
    def fake_urlopen(req, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(LlmError):
        suggest_title("本文", base_url="http://localhost:1234/v1", model="m", timeout=10)


def test_suggest_title_truncates_long_content(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(_chat_payload('{"title": "資料"}'))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    suggest_title("a" * 5000, base_url="http://localhost:1234/v1", model="m", timeout=10)

    assert len(captured["body"]["messages"][1]["content"]) == 3000
