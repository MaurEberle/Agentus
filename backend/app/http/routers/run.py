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
    # The earlier run to continue from; only with the first message.
    previous_run_id: str | None = Field(default=None, alias="previousRunId")


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


SSE_LOG_REPLAY = 1_000


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
            run_id = ctrl.run_id
            if run_id:
                from app.http.routers.runs import _camel_log
                from app.db.runs import list_logs

                # M16: a reconnect replays the tail, not every line of a long run.
                for row in list_logs(run_id, limit=SSE_LOG_REPLAY):
                    yield sse_event("log", _camel_log(row))
                for msg in list(ctrl.conversation):
                    yield sse_event(
                        "chat",
                        {"runId": run_id, "message": msg.model_dump(by_alias=True)},
                    )
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
    get_controller().send_chat(text, previous_run_id=(body.previous_run_id or "").strip() or None)
    return None


@router.get("/run/previous")
def run_previous() -> dict:
    """Earlier runs of the running network to continue from, newest first."""
    from app.run.previous_run import list_previous

    ctrl = get_controller()
    return {"items": list_previous(ctrl.network_id, ctrl.run_id)}


@router.post("/run/chat/abort", status_code=204)
def run_chat_abort():
    get_controller().abort_chat()
    return None
