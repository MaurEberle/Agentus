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
    ) -> None:
        self.error_key = error_key
        self.status = status
        self.detail = clip_error_detail(detail)
        super().__init__(error_key)


class RuntimeTransportError(RuntimeApiError):
    """Connect/timeout against the inference host."""


def map_http_status(status: int) -> str:
    if status in {401, 403}:
        return "runtime.unauthorized"
    if status == 404:
        return "runtime.modelNotFound"
    if status == 400:
        return "runtime.badRequest"
    if status >= 500:
        return "runtime.upstream"
    if status >= 400:
        return "runtime.badRequest"
    return "runtime.upstream"


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
