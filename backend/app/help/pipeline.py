from __future__ import annotations

import uuid
from collections.abc import Iterator

from app.common.secrets import mask_text
from app.db.engine import utc_now
from app.db.help_chat import HelpMessageRow, insert_message
from app.help.abort import begin_request, end_request
from app.help.index import SCORE_MIN, index_is_ready
from app.help.models import HelpMessage, HelpSource
from app.help.prompt import SYSTEM_PROMPT, build_user_packet
from app.help.retrieve import retrieve_scored
from app.help.status import effective_help_model, get_degraded, get_settings_merged, get_status
from app.http.errors import AppError
from app.http.sse import sse_event
from app.runtime.errors import RuntimeApiError
from app.runtime.models import ChatMessage, CompletionRequest, StreamEvent


def _persist(message: HelpMessage) -> None:
    insert_message(
        HelpMessageRow(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            sources=[item.model_dump(by_alias=True) for item in message.sources]
            if message.sources
            else None,
        )
    )


def _web_sources(query: str) -> list[HelpSource]:
    settings = get_settings_merged()
    help_chat = settings.help_chat
    if not help_chat.web_search_enabled or not help_chat.web_search_credential_id:
        return []
    from app.db.vault import get as vault_get
    from app.tools.execute import execute_first_party

    secret = vault_get(help_chat.web_search_credential_id)
    if not secret:
        return []
    result = execute_first_party(
        "web_search",
        config={"maxResults": 5},
        args={"query": query},
        secret=secret,
    )
    if not result.ok or not isinstance(result.result, dict):
        return []
    rows = result.result.get("results") or []
    sources: list[HelpSource] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            sources.append(
                HelpSource(
                    kind="web",
                    title=str(row.get("title") or ""),
                    url=str(row.get("url") or "") or None,
                )
            )
    return sources


def send_stream(text: str, locale: str | None = None) -> Iterator[bytes]:
    stripped = text.strip()
    if not stripped:
        raise AppError("help.empty", status_code=400)
    if not get_status().configured:
        raise AppError("help.unconfigured", status_code=400)
    event = begin_request()
    user = HelpMessage(
        id=str(uuid.uuid4()),
        role="user",
        content=mask_text(stripped),
        created_at=utc_now(),
        sources=None,
    )
    _persist(user)
    try:
        if not index_is_ready():
            yield sse_event("error", {"messageKey": "help.index.missing"})
            return
        scored = retrieve_scored(stripped, locale)
        rag_sources = [item[1] for item in scored]
        max_score = scored[0][0] if scored else 0.0
        weak = len(rag_sources) == 0 or max_score < SCORE_MIN
        web_sources: list[HelpSource] = []
        if weak:
            web_sources = _web_sources(stripped)
        sources = rag_sources + web_sources
        yield sse_event(
            "sources",
            {"sources": [item.model_dump(by_alias=True) for item in sources]},
        )
        settings = get_settings_merged()
        help_chat = settings.help_chat
        rag_lines = [
            f"- [{src.title} # {src.section}]" if src.section else f"- [{src.title}]"
            for src in rag_sources
        ]
        web_lines = [
            f"- {src.title}: {src.url or ''}"
            for src in web_sources
        ]
        user_packet = build_user_packet(stripped, rag_lines, web_lines)
        degraded = get_degraded()
        options = {"num_gpu": 0} if degraded and help_chat.provider == "ollama" else None
        from app.runtime.completions import complete_stream

        collected = ""
        try:
            stream = complete_stream(
                CompletionRequest(
                    provider=help_chat.provider,  # type: ignore[arg-type]
                    model=effective_help_model(),
                    messages=[
                        ChatMessage(role="system", content=SYSTEM_PROMPT),
                        ChatMessage(role="user", content=user_packet),
                    ],
                    credential_id=help_chat.credential_id,
                    ollama_options=options,
                    timeout_sec=120,
                )
            )
            for item in stream:
                if event.is_set():
                    break
                if not isinstance(item, StreamEvent):
                    continue
                if item.kind == "delta" and item.text:
                    collected += item.text
                    yield sse_event("delta", {"chunk": item.text})
                elif item.kind == "error":
                    yield sse_event(
                        "error",
                        {"messageKey": item.error_key or "runtime.upstream"},
                    )
                    return
        except RuntimeApiError as exc:
            yield sse_event("error", {"messageKey": exc.error_key})
            return
        assistant = HelpMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            content=mask_text(collected),
            created_at=utc_now(),
            sources=sources or None,
        )
        _persist(assistant)
        yield sse_event("done", {"message": assistant.model_dump(by_alias=True)})
    finally:
        end_request(event)
