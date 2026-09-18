from __future__ import annotations

import httpx
import pytest

from app.common.http import client as real_client
from app.tools.execute import execute_first_party


def test_missing_secret() -> None:
    result = execute_first_party("web_search", args={"query": "agentus"})
    assert result.ok is False
    assert result.error_key == "tools.webSearch.missingCredential"


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

    def wrapped(*, timeout_sec: float = 15.0, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(timeout_sec=timeout_sec, **kwargs)

    monkeypatch.setattr("app.tools.web_search_tool.client", wrapped)
    result = execute_first_party(
        "web_search", args={"query": "agentus"}, secret=token
    )
    assert result.ok is True
    assert result.result["results"][0]["url"] == "https://example.com/a"
    assert token not in str(result.result)
