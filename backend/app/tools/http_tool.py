from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx

from app.common.http import client
from app.common.secrets import mask_obj, mask_text
from app.tools.models import ExecuteResult

_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
_REDIRECTS = frozenset({301, 302, 303, 307, 308})
_BLOCKED_HOSTS = frozenset({"169.254.169.254", "metadata.google.internal"})
_MASK_HEADER_NAMES = frozenset({"authorization", "set-cookie"})


def _fail(key: str, result: object | None = None) -> ExecuteResult:
    return ExecuteResult(ok=False, error_key=key, result=mask_obj(result) if result is not None else None)


def _clamp_float(value: object, lo: float, hi: float, default: float) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


def _clamp_int(value: object, lo: int, hi: int, default: int) -> int:
    return int(_clamp_float(value, float(lo), float(hi), float(default)))


def _check_url(url: str) -> str | None:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if not url.strip():
        return "tools.http.invalidUrl"
    if scheme not in {"http", "https"}:
        return "tools.http.fileScheme"
    host = (parsed.hostname or "").lower()
    if not host:
        return "tools.http.invalidUrl"
    if host in _BLOCKED_HOSTS:
        return "tools.http.blockedHost"
    return None


def _with_query(url: str, query: object) -> str:
    parsed = urlparse(url)
    pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if isinstance(query, dict):
        for key, value in query.items():
            pairs[str(key)] = str(value)
    return urlunparse(parsed._replace(query=urlencode(pairs)))


def _mask_headers(headers: httpx.Headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        out[key] = "***" if key.lower() in _MASK_HEADER_NAMES else mask_text(value)
    return out


def _read_body(response: httpx.Response, max_bytes: int) -> tuple[str | None, str | None]:
    length = response.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > max_bytes:
                return None, "tools.http.tooLarge"
        except ValueError:
            pass
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_bytes:
            return None, "tools.http.tooLarge"
        chunks.append(chunk)
    text = b"".join(chunks).decode("utf-8", errors="replace")
    return text, None


def run(
    config: dict[str, Any] | None,
    args: dict[str, Any] | None,
    secret: str | None,
) -> ExecuteResult:
    cfg = config or {}
    argv = args or {}
    url = str(argv.get("url") or "").strip()
    if not url:
        return _fail("tools.http.invalidUrl")
    method = str(argv.get("method") or cfg.get("method") or "GET").strip().upper()
    if method not in _METHODS:
        return _fail("tools.http.invalidMethod")
    timeout = _clamp_float(cfg.get("timeoutSec"), 1.0, 60.0, 15.0)
    max_bytes = _clamp_int(cfg.get("maxBytes"), 1, 1_048_576, 65_536)
    url = _with_query(url, argv.get("query"))
    blocked = _check_url(url)
    if blocked:
        return _fail(blocked)

    headers: dict[str, str] = {}
    raw_headers = argv.get("headers")
    if isinstance(raw_headers, dict):
        headers = {str(k): str(v) for k, v in raw_headers.items()}
    if secret and not any(k.lower() == "authorization" for k in headers):
        headers["Authorization"] = f"Bearer {secret}"
    body = argv.get("body") if method in _BODY_METHODS else None
    content = None if body is None else str(body)

    current = url
    current_method = method
    try:
        with client(timeout_sec=timeout) as http:
            for _ in range(6):
                with http.stream(
                    current_method,
                    current,
                    headers=headers,
                    content=content,
                ) as response:
                    if response.status_code in _REDIRECTS:
                        location = response.headers.get("location")
                        if not location:
                            return _fail(
                                "tools.http.upstream",
                                {"status": response.status_code, "body": ""},
                            )
                        nxt = urljoin(current, location)
                        blocked = _check_url(nxt)
                        if blocked:
                            return _fail(blocked)
                        current = nxt
                        if response.status_code in {301, 302, 303}:
                            current_method = "GET"
                            content = None
                        continue
                    text, too_large = _read_body(response, max_bytes)
                    if too_large:
                        return _fail(too_large)
                    payload = {
                        "status": response.status_code,
                        "headers": _mask_headers(response.headers),
                        "body": mask_text(text or ""),
                    }
                    if response.status_code >= 400:
                        return _fail("tools.http.upstream", payload)
                    return ExecuteResult(ok=True, result=mask_obj(payload))
    except httpx.TimeoutException:
        return _fail("tools.http.timeout")
    except httpx.HTTPError:
        return _fail("tools.http.upstream")
    return _fail("tools.http.upstream")
