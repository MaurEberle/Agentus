from __future__ import annotations

import ipaddress

import httpx
import pytest

from app.common.http import client as real_client
from app.tools.execute import execute_first_party

_PUBLIC = "http://93.184.216.34/x"


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


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",
        "http://localhost/x",
        "http://[::1]/x",
        "http://[::ffff:127.0.0.1]/x",
        "http://2130706433/x",
        "http://169.254.1.1/x",
        "http://0.0.0.0/x",
        "http://224.0.0.1/x",
        "http://metadata.google.internal/x",
        "http://app.localhost/x",
    ],
)
def test_blocked_local_and_metadata_targets(url: str) -> None:
    result = execute_first_party("http", args={"url": url})
    assert result.ok is False
    assert result.error_key == "tools.http.blockedHost"


def test_private_lan_is_not_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="lan")

    _install(monkeypatch, handler)
    result = execute_first_party("http", args={"url": "http://192.168.1.10/x"})
    assert result.ok is True
    assert result.result["body"] == "lan"


def test_dns_to_loopback_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.tools.http_tool._resolved_ips",
        lambda _host: [ipaddress.ip_address("127.0.0.1")],
    )
    result = execute_first_party("http", args={"url": "http://example.test/x"})
    assert result.ok is False
    assert result.error_key == "tools.http.blockedHost"


def test_dns_failure_does_not_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.http_tool._resolved_ips", lambda _host: [])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    _install(monkeypatch, handler)
    result = execute_first_party("http", args={"url": "http://example.test/x"})
    assert result.ok is True


def test_mock_200_masks_sk_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="hello sk-abcdefghijk")

    _install(monkeypatch, handler)
    result = execute_first_party("http", args={"url": _PUBLIC})
    assert result.ok is True
    body = result.result["body"]
    assert "sk-***" in body
    assert "sk-abcdefghijk" not in body


def test_http_401_upstream_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Bearer super-token")

    _install(monkeypatch, handler)
    result = execute_first_party("http", args={"url": _PUBLIC})
    assert result.ok is False
    assert result.error_key == "tools.http.upstream"
    assert result.result["status"] == 401
    assert "super-token" not in str(result.result["body"])
    assert "Bearer ***" in result.result["body"]


def test_cross_host_redirect_drops_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str | None, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                str(request.url),
                request.headers.get("authorization"),
                request.headers.get("cookie"),
            )
        )
        if request.url.host == "93.184.216.34":
            return httpx.Response(302, headers={"location": "http://203.0.113.10/y"})
        return httpx.Response(200, text="landed")

    _install(monkeypatch, handler)
    result = execute_first_party(
        "http",
        args={
            "url": _PUBLIC,
            "headers": {"Cookie": "sid=1", "Proxy-Authorization": "Basic eA=="},
        },
        secret="dummy-bearer",
    )
    assert result.ok is True
    assert result.result["body"] == "landed"
    assert seen[0][1] == "Bearer dummy-bearer"
    assert seen[0][2] == "sid=1"
    assert seen[1][0].startswith("http://203.0.113.10/y")
    assert seen[1][1] is None
    assert seen[1][2] is None


def test_same_host_redirect_keeps_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        if request.url.path == "/x":
            return httpx.Response(302, headers={"location": "/y"})
        return httpx.Response(200, text="same")

    _install(monkeypatch, handler)
    result = execute_first_party("http", args={"url": _PUBLIC}, secret="dummy-bearer")
    assert result.ok is True
    assert seen == ["Bearer dummy-bearer", "Bearer dummy-bearer"]


def test_redirect_to_loopback_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})

    _install(monkeypatch, handler)
    result = execute_first_party("http", args={"url": _PUBLIC}, secret="dummy-bearer")
    assert result.ok is False
    assert result.error_key == "tools.http.blockedHost"
