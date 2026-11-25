"""Architect module API (fix/netz-architekt/entwurf.md)."""

from __future__ import annotations

import json
import threading
from typing import Any

from fastapi import APIRouter, Response
from pydantic import Field

from app.architect import closing, loop
from app.architect import session as sessions
from app.architect.catalog_view import live_catalog
from app.common.components import catalog_hash
from app.db import architect as store
from app.http.app import ApiModel
from app.http.errors import AppError
from app.http.sse import sse_response

router = APIRouter()
_recovered = threading.Event()


def _recover() -> None:
    """After a restart no session is running; the database may still say so."""
    if not _recovered.is_set():
        store.end_active_sessions()
        _recovered.set()


class CreateBody(ApiModel):
    provider: str
    # Empty for a chat that reads a network in before a model is picked; the start sets it.
    model: str = ""
    credential_id: str | None = Field(default=None, alias="credentialId")


class StartBody(ApiModel):
    provider: str | None = None
    model: str | None = None
    credential_id: str | None = Field(default=None, alias="credentialId")
    force_slow: bool = Field(default=False, alias="forceSlow")
    confirm_running: bool = Field(default=False, alias="confirmRunning")


class ModelCheckBody(ApiModel):
    provider: str
    model: str
    credential_id: str | None = Field(default=None, alias="credentialId")


class SendBody(ApiModel):
    text: str
    locale: str | None = None


class PatchBody(ApiModel):
    title: str | None = None
    brief: dict[str, Any] | None = None


class LoadBody(ApiModel):
    network_id: str = Field(alias="networkId")
    purpose: str = "change"


class ApplyBody(ApiModel):
    mode: str | None = None
    set_active: bool = Field(default=False, alias="setActive")
    prompts_to_library: bool = Field(default=False, alias="promptsToLibrary")
    # The user chose to save over another writer's change (networks.conflict).
    force: bool = False


def _summary(row: store.ArchitectSessionRow, messages: int | None = None) -> dict[str, Any]:
    applied = row.applied[-1] if row.applied else None
    source = row.source or {}
    changing = source.get("networkId") if source.get("purpose") == "change" else None
    draft = row.draft or {}
    out: dict[str, Any] = {
        "id": row.id,
        "title": row.title,
        "provider": row.provider,
        "model": row.model,
        "credentialId": row.credential_id,
        "state": row.state,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
        "networkId": changing or (applied or {}).get("networkId"),
        # What the session list's hover card shows, without loading the whole session.
        "goal": str((row.brief or {}).get("goal") or "").strip()[:300] or None,
        "draftName": str(draft.get("name") or "").strip() or None,
        "draftNodes": len(draft.get("nodes") or []) if row.draft else None,
        "readIn": (
            {"name": source.get("name"), "purpose": source.get("purpose"), "version": source.get("version")}
            if source.get("networkId")
            else None
        ),
        "lastApplied": (
            {
                "name": applied.get("name"),
                "mode": applied.get("mode"),
                "version": applied.get("version"),
                "undone": bool(applied.get("undone")),
            }
            if applied
            else None
        ),
    }
    if messages is not None:
        out["messageCount"] = messages
    return out


def _detail(row: store.ArchitectSessionRow) -> dict[str, Any]:
    messages = [
        {"id": item.id, "role": item.role, "content": item.content, "createdAt": item.created_at, "tools": item.tools or []}
        for item in store.list_messages(row.id)
    ]
    return {
        **_summary(row),
        **loop.state_payload(row),
        "catalogChanged": row.catalog_hash != catalog_hash(),
        "messages": messages,
    }


@router.get("/architect/catalog")
def get_catalog() -> dict[str, Any]:
    return live_catalog()


@router.get("/architect/examples")
def get_examples() -> dict[str, Any]:
    from app.architect.examples import status

    return status()


@router.post("/architect/examples/reindex")
def post_examples_reindex() -> dict[str, Any]:
    from app.architect.examples import reindex
    from app.architect.tools import app_lookup

    return reindex(app_lookup())


@router.get("/architect/status")
def get_status() -> dict[str, Any]:
    _recover()
    return sessions.status()


@router.post("/architect/model-check")
def post_model_check(body: ModelCheckBody) -> dict[str, Any]:
    checked = sessions.check_model(body.provider, body.model, body.credential_id)
    out: dict[str, Any] = {"model": checked.as_dict()}
    if checked.ok and checked.local:
        gpu = sessions.check_gpu(body.model, min(checked.context or sessions.ARCHITECT_CONTEXT, sessions.ARCHITECT_CONTEXT))
        out["gpu"] = gpu.as_dict()
    return out


@router.get("/architect/sessions")
def get_sessions() -> dict[str, Any]:
    _recover()
    counts = store.message_counts()
    return {"items": [_summary(row, counts.get(row.id, 0)) for row in store.list_sessions()]}


@router.post("/architect/sessions", status_code=201)
def post_session(body: CreateBody) -> dict[str, Any]:
    _recover()
    if body.provider not in sessions.PROVIDERS:
        raise AppError("architect.model.missing", status_code=400)
    return _summary(sessions.create(body.provider, body.model, body.credential_id))


@router.get("/architect/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    _recover()
    return _detail(sessions.require(session_id))


@router.patch("/architect/sessions/{session_id}")
def patch_session(session_id: str, body: PatchBody) -> dict[str, Any]:
    # A streaming turn holds the row and would overwrite the edit when it saves.
    row = closing.idle_session(session_id)
    if body.title is not None:
        row.title = body.title.strip()[:120]
    if body.brief is not None:
        from app.architect.tools import BRIEF_FIELDS

        row.brief = {
            key: str(value).strip()[:1000]
            for key, value in body.brief.items()
            if key in BRIEF_FIELDS and str(value or "").strip()
        }
    store.save_session(row)
    return _detail(row)


@router.delete("/architect/sessions/{session_id}", status_code=204)
def delete_session(session_id: str) -> Response:
    sessions.require(session_id)
    sessions.stop(session_id, reason="deleted")
    store.delete_session(session_id)
    return Response(status_code=204)


@router.post("/architect/sessions/{session_id}/start")
def post_start(session_id: str, body: StartBody) -> dict[str, Any]:
    _recover()
    result = sessions.start(
        session_id,
        provider=body.provider,
        model=body.model,
        credential_id=body.credential_id,
        force_slow=body.force_slow,
        confirm_running=body.confirm_running,
    )
    return {**result, "session": _summary(sessions.require(session_id)), "status": sessions.status()}


@router.post("/architect/sessions/{session_id}/stop", status_code=204)
def post_stop(session_id: str) -> Response:
    sessions.require(session_id)
    sessions.stop(session_id, reason="user")
    return Response(status_code=204)


@router.post("/architect/sessions/{session_id}/messages")
def post_message(session_id: str, body: SendBody):
    return sse_response(loop.send(session_id, body.text, body.locale))


@router.post("/architect/sessions/{session_id}/touch", status_code=204)
def post_touch(session_id: str) -> Response:
    """E-15: "Weiter arbeiten" in the idle notice counts as input."""
    sessions.touch(session_id)
    return Response(status_code=204)


@router.post("/architect/sessions/{session_id}/abort", status_code=204)
def post_abort(session_id: str) -> Response:
    sessions.abort(session_id)
    return Response(status_code=204)


@router.post("/architect/sessions/{session_id}/load")
def post_load(session_id: str, body: LoadBody) -> dict[str, Any]:
    """E-6, E-10, E-12: read a network in, only on the user's click."""
    row = closing.idle_session(session_id)
    closing.load_into(row, body.network_id, body.purpose)
    return _detail(row)


@router.post("/architect/sessions/{session_id}/proposal/dismiss")
def post_dismiss(session_id: str) -> dict[str, Any]:
    row = closing.idle_session(session_id)
    row.proposal = None
    store.save_session(row)
    return _detail(row)


@router.get("/architect/sessions/{session_id}/closing")
def get_closing(session_id: str, mode: str | None = None) -> dict[str, Any]:
    return closing.preview(sessions.require(session_id), mode)


@router.post("/architect/sessions/{session_id}/apply")
def post_apply(session_id: str, body: ApplyBody) -> dict[str, Any]:
    row = closing.idle_session(session_id)
    result = closing.apply(
        row, mode=body.mode, set_active=body.set_active, prompts_to_library=body.prompts_to_library, force=body.force
    )
    return {**result, "session": _detail(row)}


@router.post("/architect/sessions/{session_id}/undo")
def post_undo(session_id: str) -> dict[str, Any]:
    row = closing.idle_session(session_id)
    result = closing.undo(row)
    return {**result, "session": _detail(row)}


@router.get("/architect/sessions/{session_id}/export")
def get_export(session_id: str) -> dict[str, Any]:
    row = sessions.require(session_id)
    return {"name": f"{row.title or 'architekt'}.md", "markdown": export_markdown(row)}


def export_markdown(row: store.ArchitectSessionRow) -> str:
    """E-11: brief, chat and draft of a session as Markdown."""
    lines = [f"# {row.title or 'Architekt-Sitzung'}", "", f"Modell: {row.provider} · {row.model}", ""]
    if row.brief:
        lines += ["## Steckbrief", ""]
        lines += [f"- **{key}:** {value}" for key, value in row.brief.items()]
        lines.append("")
    lines += ["## Verlauf", ""]
    for item in store.list_messages(row.id):
        who = "Du" if item.role == "user" else "Architekt"
        lines += [f"### {who} · {item.created_at}", "", item.content or "", ""]
        for tool in item.tools or []:
            lines.append(f"- _{tool.get('name')}_")
        if item.tools:
            lines.append("")
    if row.draft:
        lines += ["## Entwurf", "", "```json", json.dumps(row.draft, ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines)
