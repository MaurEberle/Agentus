from __future__ import annotations

import httpx
import pytest

from app.common.http import client as real_client
from app.tools.execute import execute_first_party


def test_missing_secret() -> None:
    result = execute_first_party("web_search", args={"query": "agentus"})
    assert result.ok is False
    assert result.error_key == "tools.webSearch.missingCredential"


def _mock(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    def wrapped(*, timeout_sec: float = 15.0, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(timeout_sec=timeout_sec, **kwargs)

    monkeypatch.setattr("app.tools.web_search_tool.client", wrapped)


def test_brave_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    token = "brave-secret-token"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-subscription-token"] == token
        assert request.url.params["q"] == "agentus"
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "Agentus",
                            "url": "https://example.com/a",
                            "description": "desc",
                        }
                    ]
                }
            },
        )

    _mock(monkeypatch, handler)
    result = execute_first_party(
        "web_search", args={"query": "agentus"}, secret=token
    )
    assert result.ok is True
    assert result.result["results"][0]["url"] == "https://example.com/a"
    assert token not in str(result.result)


def test_tavily_uses_content_as_snippet(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.tavily.com"
        assert request.headers["authorization"] == "Bearer tv"
        return httpx.Response(
            200,
            json={"results": [{"title": "T", "url": "https://example.com/t", "content": "body"}]},
        )

    _mock(monkeypatch, handler)
    result = execute_first_party(
        "web_search",
        config={"searchProvider": "tavily"},
        args={"query": "agentus"},
        secret="tv",
    )
    assert result.ok is True
    assert result.result["results"][0]["snippet"] == "body"


def test_exa_uses_highlight(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "ex"
        return httpx.Response(
            200,
            json={"results": [{"title": "E", "url": "https://example.com/e", "highlights": ["hit"]}]},
        )

    _mock(monkeypatch, handler)
    result = execute_first_party(
        "web_search",
        config={"searchProvider": "exa", "maxResults": 3},
        args={"query": "agentus"},
        secret="ex",
    )
    assert result.ok is True
    assert result.result["results"][0]["snippet"] == "hit"


def test_searxng_needs_base_url_and_skips_secret() -> None:
    missing = execute_first_party(
        "web_search",
        config={"searchProvider": "searxng"},
        args={"query": "agentus"},
    )
    assert missing.error_key == "tools.webSearch.missingBaseUrl"


def test_searxng_reads_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "search.example"
        assert request.url.params["format"] == "json"
        return httpx.Response(
            200,
            json={"results": [{"title": "S", "url": "https://example.com/s", "content": "snip"}]},
        )

    _mock(monkeypatch, handler)
    result = execute_first_party(
        "web_search",
        config={"searchProvider": "searxng", "searchBaseUrl": "https://search.example/"},
        args={"query": "agentus"},
    )
    assert result.ok is True
    assert result.result["results"][0]["snippet"] == "snip"
