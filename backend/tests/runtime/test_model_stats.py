from __future__ import annotations

import httpx
import pytest

from app.runtime.model_stats import (
    context_steps,
    extract_context_max,
    get_model_stats,
    local_context_min,
    prefix_context_max,
)
from tests.runtime.transport import install_transport


def test_prefix_and_steps() -> None:
    assert prefix_context_max("grok-4.5") == 500_000
    assert prefix_context_max("gpt-4o-mini") == 128_000
    steps = context_steps(4096, 500_000)
    assert steps[0] == 4096
    assert 131072 in steps
    assert steps[-1] == 500_000


def test_local_min() -> None:
    assert local_context_min(32768) == 2048
    assert local_context_min(2048) == 512


def test_extract_gemini_and_xai_payloads() -> None:
    assert extract_context_max({"inputTokenLimit": 1_048_576}) == 1_048_576
    assert extract_context_max({"context_window": 256000}) == 256000
    assert (
        extract_context_max({"model_info": {"llama.context_length": 32768, "general.architecture": "llama"}})
        == 32768
    )


def test_ollama_uses_architecture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.runtime.model_stats.architecture_context", lambda tag, base_url=None: 16384)
    minimum, maximum, steps = get_model_stats("ollama", "llama3.2:1b")
    assert minimum == 2048
    assert maximum == 16384
    assert steps == []


def test_xai_reads_model_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/models/grok-4.5")
        return httpx.Response(200, json={"id": "grok-4.5", "context_window": 500000})

    install_transport(monkeypatch, handler)
    minimum, maximum, steps = get_model_stats("xai", "grok-4.5", credential_id=None)
    # no credential → prefix fallback
    assert maximum == 500_000
    assert 500_000 in steps
    assert minimum == 4096


def test_xai_with_secret_hits_api(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "grok-4.5", "context_window": 123456})

    install_transport(monkeypatch, handler)
    from app.runtime import model_stats as mod

    monkeypatch.setattr(mod, "resolve_secret", lambda secret, credential_id: "sk-test")
    minimum, maximum, steps = get_model_stats("xai", "grok-4.5", credential_id="cred")
    assert maximum == 123456
    assert steps[-1] == 123456
    assert minimum == 4096


def test_gemini_native_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "generativelanguage.googleapis.com" in str(request.url):
            return httpx.Response(200, json={"name": "models/gemini-2.0-flash", "inputTokenLimit": 1048576})
        return httpx.Response(404, json={"error": "missing"})

    install_transport(monkeypatch, handler)
    from app.runtime import model_stats as mod

    monkeypatch.setattr(mod, "resolve_secret", lambda secret, credential_id: "gm-key")
    _minimum, maximum, steps = get_model_stats("gemini", "gemini-2.0-flash", credential_id="c")
    assert maximum == 1_048_576
    assert 1_048_576 in steps
