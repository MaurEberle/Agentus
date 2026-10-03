from __future__ import annotations

import json

import httpx
import pytest

from app.runtime.errors import RuntimeTransportError
from app.runtime.ollama import (
    ensure_loaded,
    gpu_layers_for_percent,
    list_loaded_models,
    list_ollama_models,
    model_block_count,
    parse_block_count,
    ping_ollama,
    unload,
)
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


def test_parse_block_count() -> None:
    assert parse_block_count({"model_info": {"llama.block_count": 16}}) == 16
    assert parse_block_count({"model_info": {"qwen3.block_count": 65, "qwen3.attention.head_count": 20}}) == 65
    assert parse_block_count({}) is None
    assert parse_block_count({"model_info": {"llama.block_count": 0}}) is None
    assert parse_block_count({"model_info": {"llama.block_count": -1}}) is None


def test_parse_block_count_uses_architecture_not_dense_prefix() -> None:
    payload = {
        "model_info": {
            "general.architecture": "deepseek2",
            "deepseek2.block_count": 47,
            "deepseek2.leading_dense_block_count": 1,
        }
    }
    assert parse_block_count(payload) == 47


def test_parse_block_count_ignores_fast_and_vision() -> None:
    assert (
        parse_block_count(
            {
                "model_info": {
                    "general.architecture": "fish-speech",
                    "fish-speech.block_count": 36,
                    "fish_speech.fast_block_count": 4,
                }
            }
        )
        == 36
    )
    assert (
        parse_block_count(
            {
                "model_info": {
                    "general.architecture": "qwen3vl",
                    "qwen3vl.block_count": 28,
                    "qwen3vl.vision.block_count": 1,
                }
            }
        )
        == 28
    )


def test_gpu_layers_for_percent() -> None:
    assert gpu_layers_for_percent(100, 47) == 47
    assert gpu_layers_for_percent(10, 47) == 5
    assert gpu_layers_for_percent(50, 47) == 24
    assert gpu_layers_for_percent(10, 16) == 2
    assert gpu_layers_for_percent(100, None) == 999
    assert gpu_layers_for_percent(50, None) == 999


def test_model_block_count_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.runtime import ollama as ollama_mod

    ollama_mod._block_counts.clear()
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"model_info": {"llama.block_count": 16}})

    install_transport(monkeypatch, handler)
    assert model_block_count("llama3.2:1b") == 16
    assert model_block_count("llama3.2:1b") == 16
    assert calls == ["/api/show"]


def test_model_block_count_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.runtime import ollama as ollama_mod

    ollama_mod._block_counts.clear()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    install_transport(monkeypatch, handler)
    assert model_block_count("missing") is None
