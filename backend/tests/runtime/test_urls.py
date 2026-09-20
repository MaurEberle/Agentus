from __future__ import annotations

import pytest

from app.runtime.errors import RuntimeApiError
from app.runtime.urls import DEFAULT_XAI_BASE, completions_url, embeddings_url, models_url


def test_completions_url_ollama_root() -> None:
    url = completions_url(
        "ollama",
        ollama_root="http://127.0.0.1:11434",
        override_base=None,
        settings_openai=None,
    )
    assert url.endswith("/v1/chat/completions")
    assert "/v1/v1" not in url
    assert url == "http://127.0.0.1:11434/v1/chat/completions"


def test_completions_url_xai_default() -> None:
    url = completions_url(
        "xai",
        ollama_root="http://127.0.0.1:11434",
        override_base=None,
        settings_openai=None,
    )
    assert url == f"{DEFAULT_XAI_BASE}/chat/completions"
    assert url == "https://api.x.ai/v1/chat/completions"
    assert "/v1/v1" not in url


def test_completions_url_openai_v1() -> None:
    url = completions_url(
        "openai_compat",
        ollama_root="http://127.0.0.1:11434",
        override_base=None,
        settings_openai="http://127.0.0.1:1234/v1",
    )
    assert url == "http://127.0.0.1:1234/v1/chat/completions"


def test_embeddings_url_ollama() -> None:
    url = embeddings_url(
        "ollama",
        ollama_root="http://127.0.0.1:11434",
        override_base=None,
        settings_openai=None,
    )
    assert url == "http://127.0.0.1:11434/v1/embeddings"


def test_models_url_xai_default() -> None:
    url = models_url(
        "xai",
        ollama_root="http://127.0.0.1:11434",
        override_base=None,
        settings_openai=None,
    )
    assert url == "https://api.x.ai/v1/models"
    assert "/v1/v1" not in url


def test_openai_missing_base() -> None:
    with pytest.raises(RuntimeApiError) as err:
        completions_url(
            "openai_compat",
            ollama_root="http://127.0.0.1:11434",
            override_base=None,
            settings_openai=None,
        )
    assert err.value.error_key == "runtime.missingBaseUrl"
