"""Loopback guard: reject foreign Host and Origin headers (DNS rebinding, CSRF).

The API has no auth and relies on loopback binding. A rebinding page reaches the
socket with its own hostname in ``Host``; a cross-site form or fetch carries its
own ``Origin``. Both are refused before any router runs.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from urllib.parse import urlparse

from starlette.types import ASGIApp, Receive, Scope, Send

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _host_name(value: str) -> str:
    try:
        return (urlparse(f"//{value}").hostname or "").lower()
    except ValueError:
        return ""


def host_allowed(value: str | None) -> bool:
    return bool(value) and _host_name(value) in LOOPBACK_HOSTS


def _host_port(value: str) -> int:
    try:
        return urlparse(f"//{value}").port or 80
    except ValueError:
        return -1


def origin_allowed(
    value: str | None,
    host: str | None = None,
    extra: Iterable[str] = (),
) -> bool:
    """Missing Origin is fine (same-origin GET, non-browser clients).

    M21: a loopback origin on another port is another program (any local web page
    on localhost:3000). With ``host`` only the request's own port passes, plus the
    origins in ``extra`` (Vite in dev, AGENTUS_NETWORK_CORS_ORIGINS).
    """
    if value is None:
        return True
    try:
        parsed = urlparse(value)
        origin_port = parsed.port
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if (parsed.hostname or "").lower() not in LOOPBACK_HOSTS:
        return False
    if value.rstrip("/") in {item.rstrip("/") for item in extra}:
        return True
    if host is None:
        return True
    if origin_port is None:
        origin_port = 443 if parsed.scheme == "https" else 80
    return origin_port == _host_port(host)


def fetch_site_allowed(value: str | None) -> bool:
    """M21: browsers mark requests a foreign page starts (also ``<img>`` GETs without Origin)."""
    return (value or "").strip().lower() != "cross-site"


class LoopbackGuard:
    def __init__(self, app: ASGIApp, extra_origins: Iterable[str] = ()) -> None:
        self.app = app
        self.extra_origins = frozenset(item.rstrip("/") for item in extra_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        headers: dict[str, str] = {}
        for raw_key, raw_value in scope.get("headers") or []:
            key = raw_key.decode("latin-1").lower()
            if key in {"host", "origin", "sec-fetch-site"}:
                headers[key] = raw_value.decode("latin-1")
        if not host_allowed(headers.get("host")):
            await _reject(scope, send, "http.forbiddenHost")
            return
        if not origin_allowed(headers.get("origin"), headers.get("host"), self.extra_origins):
            await _reject(scope, send, "http.forbiddenOrigin")
            return
        if not fetch_site_allowed(headers.get("sec-fetch-site")):
            await _reject(scope, send, "http.forbiddenOrigin")
            return
        await self.app(scope, receive, send)


async def _reject(scope: Scope, send: Send, message_key: str) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1008})
        return
    body = json.dumps({"messageKey": message_key}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
