from __future__ import annotations

import json

import httpx
import pytest

from app.runtime.errors import RuntimeTransportError
from app.runtime.ollama import ensure_loaded, list_loaded_models, list_ollama_models, ping_ollama, unload
from tests.runtime.transport import install_transport


def test_ping_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/api/tags")
        return httpx.Response(200, json={"models": []})

    install_transport(monkeypatch, handler)
    result = ping_ollama()
    assert result.ok is True


def test_ping_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    install_transport(monkeypatch, handler)
    result = ping_ollama()
    assert result.ok is False
    assert result.message_key == "runtime.unreachable"


def test_list_models_names_and_size(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"models": [{"name": "llama3.2:1b", "size": 111}, {"model": "nomic-embed-text"}]},
        )

    install_transport(monkeypatch, handler)
    items = list_ollama_models()
    assert items[0].name == "llama3.2:1b"
    assert items[0].size_bytes == 111
    assert items[1].name == "nomic-embed-text"


def test_list_models_transport_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeTransportError) as err:
        list_ollama_models()
    assert err.value.error_key == "runtime.unreachable"


def test_ensure_loaded_skips_generate_when_in_ps(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/api/ps"):
            return httpx.Response(200, json={"models": [{"name": "llama3.2:1b"}]})
        raise AssertionError("unexpected generate")

    install_transport(monkeypatch, handler)
    ensure_loaded("llama3.2:1b")
    assert seen == ["GET /api/ps"]


def test_unload_keep_alive_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/generate"):
            bodies.append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"models": []})

    install_transport(monkeypatch, handler)
    unload("llama3.2:1b")
    assert bodies[0]["keep_alive"] == 0
    assert bodies[0]["model"] == "llama3.2:1b"


def test_list_loaded_uses_model_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"model": "mistral"}]})

    install_transport(monkeypatch, handler)
    assert list_loaded_models() == ["mistral"]
