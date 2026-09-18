"""SSE framing for run and help streams. Event names come from the API contract."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator

from starlette.responses import StreamingResponse

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse_event(event: str, data: object | None = None) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


def sse_comment(comment: str = "ping") -> bytes:
    return f": {comment}\n\n".encode("utf-8")


def sse_ping() -> bytes:
    return sse_comment("ping")


def sse_response(
    iterator: Iterator[bytes] | AsyncIterator[bytes],
) -> StreamingResponse:
    return StreamingResponse(
        iterator,
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
