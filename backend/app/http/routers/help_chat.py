from __future__ import annotations

from fastapi import APIRouter, Response

from app.db.help_chat import clear_messages, list_messages
from app.help.abort import abort_current
from app.help.reindex_job import begin, snapshot
from app.help.models import (
    HelpMessage,
    HelpMessageList,
    HelpReindexResult,
    HelpSendBody,
    HelpSource,
    HelpChatStatus,
)
from app.help.pipeline import send_stream
from app.help.visible import strip_think
from app.help.status import get_status, ping_help_llm
from app.http.errors import AppError
from app.http.sse import sse_response
from app.runtime.models import PingResult

router = APIRouter(tags=["help-chat"])


def _message_from_row(row) -> HelpMessage:
    sources = None
    if row.sources:
        parsed: list[HelpSource] = []
        for item in row.sources:
            if isinstance(item, dict):
                parsed.append(HelpSource.model_validate(item))
        sources = parsed or None
    return HelpMessage(
        id=row.id,
        role=row.role,  # type: ignore[arg-type]
        content=strip_think(row.content) if row.role == "assistant" else row.content,
        created_at=row.created_at,
        sources=sources,
    )


@router.get("/help-chat/status", response_model=HelpChatStatus)
def help_status() -> HelpChatStatus:
    return get_status()


@router.post("/help-chat/ping", response_model=PingResult, response_model_exclude_none=True)
def help_ping() -> PingResult:
    return ping_help_llm()


@router.get("/help-chat/messages", response_model=HelpMessageList)
def help_messages() -> HelpMessageList:
    return HelpMessageList(items=[_message_from_row(row) for row in list_messages()])


@router.post("/help-chat/messages")
def help_send(body: HelpSendBody):
    stripped = body.text.strip()
    if not stripped:
        raise AppError("help.empty", status_code=400)
    if not get_status().configured:
        raise AppError("help.unconfigured", status_code=400)
    return sse_response(send_stream(stripped, body.locale))


@router.post("/help-chat/abort", status_code=204)
def help_abort() -> Response:
    abort_current()
    return Response(status_code=204)


@router.post("/help-chat/clear", status_code=204)
def help_clear() -> Response:
    clear_messages()
    return Response(status_code=204)


def _reindex_result() -> HelpReindexResult:
    current = snapshot()
    return HelpReindexResult(
        state=current.state,
        message_key=current.message_key,
        job_id=current.job_id,
    )


@router.get("/help-chat/reindex", response_model=HelpReindexResult, response_model_exclude_none=True)
def help_reindex_status() -> HelpReindexResult:
    return _reindex_result()


@router.post("/help-chat/reindex", response_model=HelpReindexResult, response_model_exclude_none=True)
def help_reindex() -> HelpReindexResult:
    begin()
    return _reindex_result()
