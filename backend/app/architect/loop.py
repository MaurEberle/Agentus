"""One architect turn: stream the answer, run tool calls, report state changes (entwurf.md, 8 and 10).

SSE events: ``delta`` (visible text), ``tool`` (one call, start and end), ``state`` (brief, draft,
check after a change), ``done`` (the stored answer), ``error`` and ``aborted``.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterator
from typing import Any

from app.architect import session as sessions
from app.architect.prompt import system_prompt
from app.architect.tools import ArchitectTool, ToolContext, app_lookup, base_tools, run_tool, schemas
from app.common.components import catalog_hash
from app.db import architect as store
from app.db.engine import utc_now
from app.help.visible import ThinkStripper
from app.http.errors import AppError
from app.http.sse import sse_event
from app.runtime.models import ChatMessage, CompletionRequest, StreamEvent, ToolCall

log = logging.getLogger("agentus.architect")

HISTORY_MESSAGES = 16
HISTORY_CHARS = 4_000
TITLE_CHARS = 60

# The stream function; tests replace it with a fake model.
Streamer = Callable[..., Iterator[StreamEvent]]


def _default_streamer(req: CompletionRequest, *, should_abort: Callable[[], bool]) -> Iterator[StreamEvent]:
    from app.runtime.completions import complete_stream

    return complete_stream(req, should_abort=should_abort)


_streamer: Streamer = _default_streamer
# Extra tools of later packages (closing dialog, research, examples) register here.
_extra_tools: list[Callable[[], list[ArchitectTool]]] = []


def set_streamer(fn: Streamer | None) -> None:
    global _streamer
    _streamer = fn or _default_streamer


def register_tools(factory: Callable[[], list[ArchitectTool]]) -> None:
    if factory not in _extra_tools:
        _extra_tools.append(factory)


def available_tools() -> list[ArchitectTool]:
    from app.architect.closing import closing_tools
    from app.architect.examples import example_tools
    from app.architect.research import research_tools

    tools = base_tools() + closing_tools() + research_tools() + example_tools()
    for factory in _extra_tools:
        tools.extend(factory())
    return tools


def _clip(text: str) -> str:
    text = (text or "").strip()
    return text if len(text) <= HISTORY_CHARS else text[:HISTORY_CHARS].rstrip() + " …"


def _history(session_id: str) -> list[ChatMessage]:
    """Earlier exchanges, oldest first, without two user turns in a row."""
    rows = store.list_messages(session_id)[-HISTORY_MESSAGES:]
    out: list[ChatMessage] = []
    for row in rows:
        role = "assistant" if row.role == "assistant" else "user"
        if out and out[-1].role == role:
            out[-1] = ChatMessage(role=role, content=_clip(f"{out[-1].content}\n\n{row.content}"))
            continue
        out.append(ChatMessage(role=role, content=_clip(row.content)))
    while out and out[0].role != "user":
        out.pop(0)
    return out


def current_check(row: store.ArchitectSessionRow, lookup=None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """The compiled document and check of the session's draft, or (None, None)."""
    if not row.draft or not row.draft.get("nodes"):
        return None, None
    from app.architect.draft import report
    from app.architect.tools import compile_for

    compiled = compile_for(row, (lookup or app_lookup)())
    return compiled.document, report(compiled)


def state_payload(row: store.ArchitectSessionRow) -> dict[str, Any]:
    """What the page shows of a session's work: brief, draft, document, check, read-in network."""
    from app.architect.closing import public_source, source_diff

    document, check = current_check(row)
    return {
        "brief": row.brief,
        "draft": row.draft,
        "document": document,
        "check": check,
        "ids": row.ids,
        "proposal": row.proposal,
        "source": public_source(row.source),
        "applied": row.applied,
        "diff": source_diff(row, document),
    }


def send(session_id: str, text: str, locale: str | None) -> Iterator[bytes]:
    """Run one user turn of the active session as SSE."""
    active = sessions.active()
    if active is None or active.session_id != session_id:
        raise AppError("architect.notActive", status_code=409)
    if active.generating:
        raise AppError("architect.busy", status_code=409)
    row = sessions.require(session_id)
    stripped = text.strip()
    if not stripped:
        raise AppError("architect.empty", status_code=400)
    abort = sessions.set_generating(session_id, True)
    return _turn(row, stripped, locale, abort)


def _turn(row: store.ArchitectSessionRow, text: str, locale: str | None, abort) -> Iterator[bytes]:
    from app.settings.service import load_settings

    settings = load_settings().architect
    active = sessions.active()
    history = _history(row.id)
    user_id = str(uuid.uuid4())
    now = utc_now()
    store.insert_message(store.ArchitectMessageRow(id=user_id, session_id=row.id, role="user", content=text, created_at=now))
    if not row.title:
        row.title = text.splitlines()[0][:TITLE_CHARS]
    row.last_input_at = now
    tools = available_tools()
    tool_names = {tool.name for tool in tools}
    lookup_cache: dict[str, Any] = {}

    def lookup():
        if "value" not in lookup_cache:
            lookup_cache["value"] = app_lookup()
        return lookup_cache["value"]

    ctx = ToolContext(
        session=row,
        cloud=bool(active and not active.local),
        lookup=lookup,
        send_paths=settings.send_paths_to_cloud,
    )
    _, check = current_check(row, lookup)
    messages: list[ChatMessage] = [
        ChatMessage(
            role="system",
            content=system_prompt(
                locale=locale,
                tool_names=tool_names,
                brief=row.brief,
                draft=row.draft,
                check=check,
                catalog_changed=row.catalog_hash != catalog_hash(),
                source=row.source,
                applied=row.applied,
            ),
        ),
        *history,
        ChatMessage(role="user", content=text),
    ]
    budget = settings.tool_calls_per_answer
    used = 0
    visible = ThinkStripper()
    answer = ""
    tool_log: list[dict[str, Any]] = []
    try:
        while True:
            offer_tools = used < budget
            if not offer_tools:
                messages.append(
                    ChatMessage(role="user", content="(Tool limit for this answer reached. Answer the user now with what you have.)")
                )
            req = CompletionRequest(
                provider=row.provider,  # type: ignore[arg-type]
                model=row.model,
                credential_id=row.credential_id,
                messages=messages,
                tools=schemas(tools) if offer_tools else None,
                timeout_sec=300.0,
                ollama_options={"num_ctx": active.num_ctx} if active and active.num_ctx else None,
            )
            calls: list[ToolCall] = []
            step_text = ""
            failed: StreamEvent | None = None
            # Text of a new step after tool calls starts a new paragraph.
            gap = "\n\n" if answer.strip() and not answer.endswith("\n") else ""
            for event in _streamer(req, should_abort=abort.is_set):
                if event.kind == "delta" and event.text:
                    shown = visible.feed(event.text)
                    if shown:
                        if gap and not step_text:
                            shown = gap + shown.lstrip()
                        step_text += shown
                        yield sse_event("delta", {"chunk": shown})
                elif event.kind == "tool_call_delta" and event.tool_calls:
                    calls = list(event.tool_calls)
                elif event.kind == "done" and event.tool_calls:
                    calls = list(event.tool_calls)
                elif event.kind == "error":
                    failed = event
                    break
            tail = visible.finish()
            if tail:
                if gap and not step_text:
                    tail = gap + tail.lstrip()
                step_text += tail
                yield sse_event("delta", {"chunk": tail})
            answer += step_text
            if abort.is_set():
                _finish(row, answer, tool_log, aborted=True)
                yield sse_event("aborted", {})
                return
            if failed is not None:
                yield sse_event("error", {"messageKey": failed.error_key or "architect.failed", "detail": failed.error_detail})
                if answer.strip():
                    _finish(row, answer, tool_log)
                else:
                    store.save_session(row)
                return
            if not calls or not offer_tools:
                break
            messages.append(ChatMessage(role="assistant", content=step_text or None, tool_calls=calls))
            for call in calls:
                if used >= budget:
                    messages.append(
                        ChatMessage(role="tool", tool_call_id=call.id, name=call.name, content='{"error":"tool limit reached"}')
                    )
                    continue
                used += 1
                yield sse_event("tool", {"id": call.id, "name": call.name, "status": "running"})
                ctx.changed.clear()
                result = run_tool(tools, ctx, call.name, call.arguments)
                line = {"name": call.name, "key": result.key, "params": result.params, "ok": result.ok}
                tool_log.append(line)
                yield sse_event("tool", {"id": call.id, "status": "done" if result.ok else "failed", **line})
                messages.append(ChatMessage(role="tool", tool_call_id=call.id, name=call.name, content=result.content))
                if ctx.changed:
                    store.save_session(row)
                    yield sse_event("state", state_payload(row))
            if abort.is_set():
                _finish(row, answer, tool_log, aborted=True)
                yield sse_event("aborted", {})
                return
        message = _finish(row, answer, tool_log)
        yield sse_event("done", {"message": message})
    except Exception:
        log.exception("architect turn failed")
        yield sse_event("error", {"messageKey": "architect.failed"})
        store.save_session(row)
    finally:
        sessions.set_generating(row.id, False)


def _finish(row: store.ArchitectSessionRow, answer: str, tool_log: list[dict[str, Any]], *, aborted: bool = False) -> dict[str, Any]:
    text = answer.strip()
    if aborted and text:
        text += " …"
    now = utc_now()
    message_id = str(uuid.uuid4())
    if text or tool_log:
        store.insert_message(
            store.ArchitectMessageRow(
                id=message_id, session_id=row.id, role="assistant", content=text, created_at=now, tools=tool_log or None
            )
        )
    row.updated_at = now
    store.save_session(row)
    return {"id": message_id, "role": "assistant", "content": text, "createdAt": now, "tools": tool_log}
