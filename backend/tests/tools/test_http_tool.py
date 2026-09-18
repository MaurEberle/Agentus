from __future__ import annotations

import httpx
import pytest

from app.common.http import client as real_client
from app.tools.execute import execute_first_party


def _install(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    def wrapped(*, timeout_sec: float = 15.0, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(timeout_sec=timeout_sec, **kwargs)

    monkeypatch.setattr("app.tools.http_tool.client", wrapped)


def test_file_scheme_no_read() -> None:
    result = execute_first_party("http", args={"url": "file:///etc/passwd"})
    assert result.ok is False
    assert result.error_key == "tools.http.fileScheme"


def test_blocked_metadata_host() -> None:
    result = execute_first_party(
        "http", args={"url": "http://169.254.169.254/latest/meta-data"}
    )
    assert result.ok is False
    assert result.error_key == "tools.http.blockedHost"


def test_mock_200_masks_sk_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="hello sk-abcdefghijk")

    _install(monkeypatch, handler)
    result = execute_first_party("http", args={"url": "http://127.0.0.1/x"})
    assert result.ok is True
    body = result.result["body"]
    assert "sk-***" in body
    assert "sk-abcdefghijk" not in body


def test_http_401_upstream_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Bearer super-token")

    _install(monkeypatch, handler)
    result = execute_first_party("http", args={"url": "http://127.0.0.1/x"})
    assert result.ok is False
    assert result.error_key == "tools.http.upstream"
    assert result.result["status"] == 401
    assert "super-token" not in str(result.result["body"])
    assert "Bearer ***" in result.result["body"]
