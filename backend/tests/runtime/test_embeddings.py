from __future__ import annotations

import httpx
import pytest

from app.runtime.embeddings import embed
from app.runtime.models import EmbedRequest
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


def test_embed_empty_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("embed [] must not HTTP")

    install_transport(monkeypatch, handler)
    result = embed(EmbedRequest(texts=[], model="nomic-embed-text"))
    assert result.vectors == []
    assert result.dimension == 0
    assert result.model == "nomic-embed-text"
