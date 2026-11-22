"""Map transport/HTTP failures to runtime.* message keys."""

from __future__ import annotations

import re

import httpx

_TRUNCATED_TOOL_MARKERS = (
    "invalid tool call arguments",
    "failed to parse tool call arguments",
)
_TRUNCATED_TOOL_NAME = re.compile(r'for "([^"]+)"')

ERROR_DETAIL_MAX = 500
# H11: a provider that throttles (HTTP 429) is asked again, a few times and not forever.
RATE_LIMIT_RETRIES = 3
# A longer wait than this is not sat out inside one model call.
RATE_LIMIT_WAIT_MAX = 60.0
_RATE_LIMIT_BACKOFF = (2.0, 5.0, 10.0)


def clip_error_detail(text: str | None) -> str | None:
    collapsed = " ".join(str(text or "").split())
    if not collapsed:
        return None
    if len(collapsed) > ERROR_DETAIL_MAX:
        return collapsed[: ERROR_DETAIL_MAX - 1] + "…"
    return collapsed


class RuntimeApiError(Exception):
    def __init__(
        self,
        error_key: str,
        status: int | None = None,
        detail: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        self.error_key = error_key
        self.status = status
        self.detail = clip_error_detail(detail)
        # Seconds the provider asked us to wait (HTTP 429), when it said so.
        self.retry_after = retry_after
        super().__init__(error_key)


class RuntimeTransportError(RuntimeApiError):
    """Connect/timeout against the inference host."""


def map_http_status(status: int) -> str:
    if status in {401, 403}:
        return "runtime.unauthorized"
    if status == 404:
        return "runtime.modelNotFound"
    if status == 429:
        # Not a bad request: the same call works a moment later.
        return "runtime.rateLimited"
    if status == 400:
        return "runtime.badRequest"
    if status >= 500:
        return "runtime.upstream"
    if status >= 400:
        return "runtime.badRequest"
    return "runtime.upstream"


def retry_after_seconds(headers: object) -> float | None:
    """Wait the provider asks for: ``retry-after-ms``, or ``Retry-After`` in seconds or as a date."""
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    raw_ms = getter("retry-after-ms")
    if raw_ms:
        try:
            return max(0.0, float(raw_ms) / 1000.0)
        except (TypeError, ValueError):
            pass
    raw = getter("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        pass
    try:
        from datetime import datetime, timezone
        from email.utils import parsedate_to_datetime

        when = parsedate_to_datetime(str(raw))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def rate_limit_wait(retry_after: float | None, attempt: int) -> float | None:
    """Seconds before retry number ``attempt`` (from 0). None: do not wait, report the limit."""
    if retry_after is not None:
        if retry_after > RATE_LIMIT_WAIT_MAX:
            return None
        return max(0.5, retry_after)
    return _RATE_LIMIT_BACKOFF[min(max(attempt, 0), len(_RATE_LIMIT_BACKOFF) - 1)]


def is_timeout_error(exc: BaseException) -> bool:
    return isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout))


def transport_error_key(exc: BaseException) -> str:
    if is_timeout_error(exc):
        return "runtime.timeout"
    return "runtime.unreachable"


def raise_transport(exc: BaseException) -> None:
    raise RuntimeTransportError(transport_error_key(exc)) from exc


def raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 200:
        return
    detail = None
    try:
        detail = clip_error_detail(response.text)
    except Exception:
        detail = None
    raise RuntimeApiError(
        map_http_status(response.status_code),
        status=response.status_code,
        detail=detail,
        retry_after=retry_after_seconds(response.headers) if response.status_code == 429 else None,
    )


def response_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeApiError("runtime.badRequest", detail="invalid json") from exc


def is_transport_error(exc: BaseException) -> bool:
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))


def truncated_tool_call_name(exc: BaseException) -> str | None:
    """Tool name when llama-server rejected truncated tool-call JSON."""
    if not isinstance(exc, RuntimeApiError):
        return None
    if exc.error_key != "runtime.badRequest":
        return None
    detail = exc.detail or ""
    lowered = detail.lower()
    if not any(marker in lowered for marker in _TRUNCATED_TOOL_MARKERS):
        if "tool call" not in lowered or "unexpected end" not in lowered:
            return None
    match = _TRUNCATED_TOOL_NAME.search(detail)
    return match.group(1) if match else "tool"
