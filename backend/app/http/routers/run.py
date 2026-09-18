from __future__ import annotations

import queue
from typing import Any

from fastapi import APIRouter
from pydantic import Field

from app.http.app import ApiModel
from app.http.errors import AppError
from app.http.sse import sse_comment, sse_event, sse_response
from app.run.controller import get_controller
from app.run.sse import subscribe, unsubscribe

router = APIRouter(tags=["run"])


class ChatBody(ApiModel):
    text: str


class StartResponse(ApiModel):
    service_status: str = Field(alias="serviceStatus")
    run_id: str | None = Field(default=None, alias="runId")


@router.post("/run/start")
def run_start() -> dict[str, Any]:
    return get_controller().start()


@router.post("/run/stop")
def run_stop() -> dict[str, Any]:
    return get_controller().stop()


@router.get("/run")
def run_get() -> Any:
    snap = get_controller().snapshot
    if snap is None:
        return None
    return snap.model_dump(by_alias=True)


@router.get("/run/stream")
def run_stream():
    ctrl = get_controller()
    q = subscribe()

    def gen():
        try:
            yield sse_event(
                "service",
                {"serviceStatus": ctrl.service_status},
            )
            if ctrl.snapshot is not None:
                yield sse_event("run", ctrl.snapshot.model_dump(by_alias=True))
            while True:
                try:
                    event, data = q.get(timeout=15)
                    yield sse_event(event, data)
                except queue.Empty:
                    yield sse_comment("ping")
        finally:
            unsubscribe(q)

    return sse_response(gen())


@router.post("/run/chat", status_code=204)
def run_chat(body: ChatBody):
    text = body.text.strip()
    if not text:
        raise AppError("help.empty", status_code=400)
    get_controller().send_chat(text)
    return None


@router.post("/run/chat/abort", status_code=204)
def run_chat_abort():
    get_controller().abort_chat()
    return None
