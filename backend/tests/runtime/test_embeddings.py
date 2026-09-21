from __future__ import annotations

import json

import httpx
import pytest

from app.runtime.embeddings import embed
from app.runtime.errors import RuntimeApiError
from app.runtime.models import EmbedRequest, EmbedResult
from tests.runtime.transport import install_transport


def test_embed_two_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"input" in request.content
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )

    install_transport(monkeypatch, handler)
    result = embed(
        EmbedRequest(texts=["a", "b"], model="nomic-embed-text", provider="ollama")
    )
    assert len(result.vectors) == 2
    assert result.dimension == 2
    assert result.vectors[0] == [1.0, 0.0]
    assert result.vectors[1] == [0.0, 1.0]


def test_embed_batches_keep_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.runtime.embeddings._BATCH", 2)
    seen: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(list(body["input"]))
        data = [
            {"index": index, "embedding": [float(index), 1.0]}
            for index in range(len(body["input"]))
        ]
        return httpx.Response(200, json={"data": data})

    install_transport(monkeypatch, handler)
    result = embed(EmbedRequest(texts=["a", "b", "c"], model="m", provider="ollama"))
    assert seen == [["a", "b"], ["c"]]
    assert result.vectors == [[0.0, 1.0], [1.0, 1.0], [0.0, 1.0]]
    assert result.dimension == 2


def test_embed_accepts_nested_values(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": {"values": [0.5, 0.25]}}]},
        )

    install_transport(monkeypatch, handler)
    result = embed(EmbedRequest(texts=["a"], model="m", provider="gemini", secret="k"))
    assert result.vectors == [[0.5, 0.25]]


def test_embed_501_uses_forced_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.runtime.ollama_embed_runner as runner

    def _forced(req: EmbedRequest):
        assert req.model == "vl"
        return EmbedResult(vectors=[[0.25, 0.5]], dimension=2, model=req.model)

    monkeypatch.setattr(runner, "embed_with_forced_runner", _forced)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(501, json={"error": {"message": "no embeddings"}})

    install_transport(monkeypatch, handler)
    result = embed(EmbedRequest(texts=["a"], model="vl", provider="ollama"))
    assert result.vectors == [[0.25, 0.5]]


def test_embed_501_is_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(501, json={"error": {"message": "no embeddings"}})

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as caught:
        embed(EmbedRequest(texts=["a"], model="vl", provider="ollama"))
    assert caught.value.error_key == "runtime.embedUnsupported"


def test_embed_empty_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("embed [] must not HTTP")

    install_transport(monkeypatch, handler)
    result = embed(EmbedRequest(texts=[], model="nomic-embed-text"))
    assert result.vectors == []
    assert result.dimension == 0
    assert result.model == "nomic-embed-text"
