"""Uniform JSON errors: ``{ messageKey, message? }``. No stacks, no secrets."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.secrets import mask_text

log = logging.getLogger("agentus.http")


class AppError(Exception):
    def __init__(
        self,
        message_key: str,
        *,
        status_code: int = 400,
        message: str | None = None,
    ) -> None:
        self.message_key = message_key
        self.status_code = status_code
        self.message = message
        super().__init__(message_key)


def error_payload(message_key: str, message: str | None = None) -> dict[str, str]:
    body: dict[str, str] = {"messageKey": message_key}
    if message is not None:
        body["message"] = mask_text(message)
    return body


def error_response(
    status_code: int, message_key: str, message: str | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=error_payload(message_key, message)
    )


def persist_status(message_key: str) -> int:
    if message_key in {"dataDir.busy", "credentials.inUse"}:
        return 409
    if message_key == "db.notFound" or message_key.endswith(".notFound"):
        return 404
    if message_key.startswith("dataDir.") or message_key.startswith("store."):
        return 400
    if message_key.startswith("mcp.") or message_key.startswith("graph.mcp."):
        return 404 if message_key.endswith("notFound") else 400
    if message_key in {
        "run.busy",
        "run.noActiveNetwork",
        "run.invalidNetwork",
        "run.knowledge.failed",
        "dataDir.busy",
    }:
        return 409
    if message_key.startswith("graph.") or message_key.startswith("run."):
        return 409 if message_key in {"run.busy"} else 400
    return 500


def _first_validation_message(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "invalid"
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ()))
    msg = str(first.get("msg", "invalid"))
    return f"{loc}: {msg}" if loc else msg


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.message_key, exc.message)

    try:
        from app.db.errors import PersistError
    except ImportError:
        PersistError = None  # type: ignore[misc, assignment]

    if PersistError is not None:

        @app.exception_handler(PersistError)
        async def persist_error_handler(
            _request: Request, exc: Any
        ) -> JSONResponse:
            key = str(getattr(exc, "message_key", "http.internal"))
            return error_response(persist_status(key), key)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(400, "http.validation", _first_validation_message(exc))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        key = "http.notFound" if exc.status_code == 404 else "http.error"
        detail = exc.detail if isinstance(exc.detail, str) else None
        return error_response(exc.status_code, key, detail)

    @app.exception_handler(Exception)
    async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("%s", mask_text(str(exc)))
        return error_response(500, "http.internal")
