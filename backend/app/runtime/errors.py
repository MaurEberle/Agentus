"""Map transport/HTTP failures to runtime.* message keys."""

from __future__ import annotations

import httpx


class RuntimeApiError(Exception):
    def __init__(self, error_key: str, status: int | None = None) -> None:
        self.error_key = error_key
        self.status = status
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


def raise_transport(exc: BaseException) -> None:
    raise RuntimeTransportError("runtime.unreachable") from exc


def raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 200:
        return
    raise RuntimeApiError(
        map_http_status(response.status_code), status=response.status_code
    )


def response_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeApiError("runtime.badRequest") from exc


def is_transport_error(exc: BaseException) -> bool:
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))
