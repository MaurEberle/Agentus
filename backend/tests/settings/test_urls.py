from __future__ import annotations

import pytest

from app.settings.urls import normalize_ollama_base_url, normalize_optional_http_url


def test_strips_v1_and_slash() -> None:
    assert (
        normalize_ollama_base_url("http://127.0.0.1:11434/v1/")
        == "http://127.0.0.1:11434"
    )
    assert (
        normalize_ollama_base_url(" https://example.com:1234/v1 ")
        == "https://example.com:1234"
    )


def test_rejects_file_and_empty() -> None:
    with pytest.raises(ValueError, match="settings.ollamaUrl.invalid"):
        normalize_ollama_base_url("file:///tmp/ollama")
    with pytest.raises(ValueError, match="settings.ollamaUrl.invalid"):
        normalize_ollama_base_url("")
    with pytest.raises(ValueError, match="settings.ollamaUrl.invalid"):
        normalize_ollama_base_url("not-a-url")


def test_optional_keeps_v1() -> None:
    assert normalize_optional_http_url(None) is None
    assert normalize_optional_http_url("  ") is None
    assert (
        normalize_optional_http_url("http://127.0.0.1:1234/v1/")
        == "http://127.0.0.1:1234/v1"
    )
