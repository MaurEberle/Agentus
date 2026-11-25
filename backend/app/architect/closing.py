"""Reading networks in, the closing dialog, applying and undoing (fix/netz-architekt/entwurf.md, 3 and 7.3).

Nothing here writes a network on the model's word alone: ``load_network``, ``propose_create`` and
``propose_update`` only leave a proposal in the session. The page shows it, and the endpoints that
read in, create or change run on the user's click (E-5, E-6).
"""

from __future__ import annotations

import copy
from typing import Any

from app.architect import session as sessions
from app.architect.draft import Compiled, decompile, report
from app.architect.tools import ArchitectTool, ToolContext, ToolResult, _json, _object, app_lookup, compile_for
from app.db import architect as store
from app.db.engine import utc_now
from app.http.errors import AppError
from app.networks.diff import diff_documents

PURPOSES = ("change", "template")
APPLIED_KEPT = 20
_PROMPT_TYPES = frozenset({"agent", "orchestrator"})


# --- session helpers -------------------------------------------------------------------------------


def idle_session(session_id: str) -> store.ArchitectSessionRow:
    """The session, unless an answer is streaming: the turn holds the row and would overwrite changes."""
    row = sessions.require(session_id)
    active = sessions.active()
    if active is not None and active.session_id == session_id and active.generating:
        raise AppError("architect.busy", status_code=409)
    return row


def public_source(source: dict[str, Any] | None) -> dict[str, Any] | None:
    """The read-in network for the page, without its stored document."""
    if not source:
        return None
    return {key: value for key, value in source.items() if key != "base"}


def source_diff(row: store.ArchitectSessionRow, document: dict[str, Any] | None) -> dict[str, Any] | None:
    """What the draft changes on the network read in; None without one or for a template."""
    source = row.source or {}
    base = source.get("base")
    if source.get("purpose") != "change" or not isinstance(base, dict) or document is None:
        return None
    return diff_documents(base, document)


def _is_cloud(row: store.ArchitectSessionRow) -> bool:
    return row.provider != "ollama"


def _base_of(document: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(value) for key, value in document.items() if key not in {"knowledge", "version", "revision"}}


def _running_id() -> str | None:
    from app.networks.service import _running_id as running

    return running()


# --- reading in ---------------------------------------------------------------------------------------


def load_into(row: store.ArchitectSessionRow, network_id: str, purpose: str) -> dict[str, Any]:
    """Replace the draft with a stored network, to change it or as a template (E-10, E-12)."""
    from app.networks.service import get_network_document
    from app.settings.service import load_settings

    if purpose not in PURPOSES:
        raise AppError("architect.load.purpose", status_code=400)
    document = get_network_document(network_id)
    hide = _is_cloud(row) and not load_settings().architect.send_paths_to_cloud
    read = decompile(document, app_lookup(), hide_paths=hide, template=purpose == "template")
    row.draft = read.draft
    row.ids = read.ids
    row.source = {
        "networkId": network_id,
        "name": document.get("name") or "",
        "purpose": purpose,
        "version": document.get("version"),
        "revision": document.get("revision"),
        "hidden": read.hidden,
        "loadedAt": utc_now(),
        "base": read.base,
    }
    row.proposal = None
    row.updated_at = utc_now()
    store.save_session(row)
    return public_source(row.source) or {}


# --- tools ----------------------------------------------------------------------------------------------


def _find_network(text: str) -> Any:
    from app.db.networks import get_network, list_networks

    found = get_network(text)
    if found is not None:
        return found
    lowered = text.strip().lower()
    return next((item for item in list_networks() if item.name.strip().lower() == lowered), None)


def _load_network(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    text = str(args.get("id") or "").strip()
    purpose = args.get("purpose") if args.get("purpose") in PURPOSES else "change"
    found = _find_network(text) if text else None
    if found is None:
        return ToolResult(
            _json({"error": f"No network '{text}'. list_networks shows ids and names."}),
            "architect.tool.loadMissing",
            {"name": text},
            ok=False,
        )
    ctx.session.proposal = {"kind": "load", "networkId": found.id, "name": found.name, "purpose": purpose}
    ctx.changed.add("proposal")
    return ToolResult(
        _json(
            {
                "status": "waiting for the user",
                "note": "The user now sees a request to read this network in. Once confirmed, it becomes your draft "
                "and the next turn shows it. Do not guess its content; wait for the user.",
            }
        ),
        "architect.tool.loadAsk",
        {"name": found.name},
    )


def _propose(kind: str):
    def run(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
        if not (ctx.session.draft or {}).get("nodes"):
            return ToolResult(_json({"error": "There is no draft yet."}), "architect.tool.proposeBlocked", {"count": 0}, ok=False)
        compiled = compile_for(ctx.session, ctx.lookup())
        if compiled.errors:
            errors = [item.as_dict() for item in compiled.errors][:10]
            return ToolResult(
                _json({"error": "The draft still has errors; fix them before proposing.", "errors": errors}),
                "architect.tool.proposeBlocked",
                {"count": len(compiled.errors)},
                ok=False,
            )
        source = ctx.session.source or {}
        if kind == "update" and not (source.get("purpose") == "change" and source.get("networkId")):
            return ToolResult(
                _json({"error": "No network is read in to change. Use propose_create, or load_network first."}),
                "architect.tool.proposeBlocked",
                {"count": 0},
                ok=False,
            )
        ctx.session.proposal = {"kind": kind, "summary": str(args.get("summary") or "").strip()[:1500], "createdAt": utc_now()}
        ctx.changed.add("proposal")
        return ToolResult(
            _json(
                {
                    "status": "closing dialog open",
                    "note": "The user reviews summary, changes and risks and confirms or cancels. Nothing is saved yet; "
                    "do not claim it is. Wait for the user.",
                }
            ),
            "architect.tool.proposed" if kind == "create" else "architect.tool.proposedUpdate",
            {},
        )

    return run


def closing_tools() -> list[ArchitectTool]:
    summary = _object({"summary": {"type": "string", "description": "Two to five sentences: what the network does, how it is built, what to watch out for."}})
    return [
        ArchitectTool(
            "load_network",
            "Ask the user to read in one of their networks (id or exact name from list_networks): purpose 'change' to "
            "edit it, 'template' to start a new network from it. It is read in only after the user confirms.",
            _object({"id": {"type": "string"}, "purpose": {"type": "string", "enum": list(PURPOSES)}}, ["id"]),
            _load_network,
        ),
        ArchitectTool(
            "propose_create",
            "Open the closing dialog to create the draft as a new network. Only with a valid draft and when the user wants it.",
            summary,
            _propose("create"),
        ),
        ArchitectTool(
            "propose_update",
            "Open the closing dialog to save the draft into the network read in with load_network (purpose 'change').",
            summary,
            _propose("update"),
        ),
    ]


# --- closing dialog -----------------------------------------------------------------------------------


def _mode(row: store.ArchitectSessionRow, wanted: str | None) -> str:
    source = row.source or {}
    changing = source.get("purpose") == "change" and bool(source.get("networkId"))
    if wanted == "update" and not changing:
        raise AppError("architect.apply.noTarget", status_code=400)
    if wanted in {"create", "update"}:
        return wanted
    kind = (row.proposal or {}).get("kind")
    if kind in {"create", "update"}:
        return "update" if kind == "update" and changing else "create"
    return "update" if changing else "create"


def _stats(document: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    models: list[str] = []
    tools: list[str] = []
    for node in document.get("nodes") or []:
        node_type = str(node.get("type"))
        counts[node_type] = counts.get(node_type, 0) + 1
        data = node.get("data") or {}
        if node_type == "llm":
            label = " · ".join(str(part) for part in (data.get("provider"), data.get("model")) if part)
            if label and label not in models:
                models.append(label)
        if node_type == "tool" and data.get("kind") and data["kind"] not in tools:
            tools.append(str(data["kind"]))
    return {"counts": counts, "models": models, "tools": tools, "edges": len(document.get("edges") or [])}


def _prompts(document: dict[str, Any], refs: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for node in document.get("nodes") or []:
        text = str((node.get("data") or {}).get("systemPrompt") or "").strip()
        if node.get("type") in _PROMPT_TYPES and text:
            data = node.get("data") or {}
            out.append({"id": node["id"], "ref": refs.get(node["id"]), "name": data.get("displayName") or refs.get(node["id"]), "chars": len(text)})
    return out


def _compiled(row: store.ArchitectSessionRow) -> Compiled:
    if not (row.draft or {}).get("nodes"):
        raise AppError("architect.apply.empty", status_code=400)
    return compile_for(row, app_lookup())


def preview(row: store.ArchitectSessionRow, wanted: str | None = None) -> dict[str, Any]:
    """Everything the closing dialog shows (entwurf.md, 3 step 7)."""
    from app.db.networks import get_network
    from app.networks.service import get_network_document

    mode = _mode(row, wanted)
    compiled = _compiled(row)
    refs = {node_id: ref for ref, node_id in compiled.ids.items()}
    source = row.source or {}
    target: dict[str, Any] | None = None
    diff = None
    changed_since = False
    if mode == "update":
        stored = get_network(str(source.get("networkId")))
        if stored is None:
            raise AppError("networks.notFound", status_code=404)
        current = get_network_document(stored.id)
        diff = diff_documents(current, compiled.document)
        changed_since = stored.revision != source.get("revision")
        target = {"id": stored.id, "name": stored.name, "version": stored.version, "revision": stored.revision}
    check = report(compiled)
    risks = [item.as_dict() for item in compiled.hints if (item.key or "").startswith("risk.")]
    return {
        "mode": mode,
        "target": target,
        "name": compiled.document.get("name") or "",
        "description": compiled.document.get("description") or "",
        "summary": (row.proposal or {}).get("summary") or "",
        "document": compiled.document,
        "ids": compiled.ids,
        "check": check,
        "diff": diff,
        "changedSince": changed_since,
        "running": mode == "update" and _running_id() == (target or {}).get("id"),
        "networkRunning": _running_id() is not None,
        "risks": risks,
        "prompts": _prompts(compiled.document, refs),
        "stats": _stats(compiled.document),
        "canUndo": undo_entry(row) is not None,
    }


# --- applying and undoing --------------------------------------------------------------------------------


def _prompts_to_library(document: dict[str, Any], refs: dict[str, str]) -> int:
    """E-13: only on request; a text already in the library is not added twice."""
    from app.db.prompts import list_prompts
    from app.prompts.service import create_item

    known = {row.body.strip() for row in list_prompts()}
    network = str(document.get("name") or "").strip()
    added = 0
    for node in document.get("nodes") or []:
        data = node.get("data") or {}
        text = str(data.get("systemPrompt") or "").strip()
        if node.get("type") not in _PROMPT_TYPES or not text or text in known:
            continue
        label = str(data.get("displayName") or refs.get(node["id"]) or node.get("type"))
        create_item({"name": f"{network} – {label}" if network else label, "tags": ["architekt"], "body": text})
        known.add(text)
        added += 1
    return added


def apply(
    row: store.ArchitectSessionRow,
    *,
    mode: str | None = None,
    set_active: bool = False,
    prompts_to_library: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Create the network or save the change, as a version with source ``architect`` (E-17)."""
    from app.db.networks import get_network
    from app.networks.service import create_network, replace_network
    from app.settings.service import set_active_network

    chosen = _mode(row, mode)
    compiled = _compiled(row)
    if compiled.errors:
        raise AppError("architect.apply.invalid", status_code=400)
    note = (row.title or compiled.document.get("name") or "").strip()[:200] or None
    source = row.source or {}
    document = {key: value for key, value in compiled.document.items() if key not in {"knowledge", "version", "revision"}}
    previous: int | None = None
    if chosen == "update":
        stored = get_network(str(source.get("networkId")))
        if stored is None:
            raise AppError("networks.notFound", status_code=404)
        previous = stored.version
        # Raises run.busy while it runs and networks.conflict when it changed since reading in.
        saved = replace_network(
            stored.id,
            document,
            base_revision=None if force else source.get("revision"),
            new_version=True,
            note=note,
            source="architect",
        )
    else:
        document.pop("id", None)
        document.pop("isActive", None)
        saved = create_network(document, source="architect", note=note)
    entry = {
        "networkId": saved["id"],
        "name": saved.get("name") or "",
        "mode": chosen,
        "version": saved.get("version"),
        "revision": saved.get("revision"),
        "previousVersion": previous,
        "changed": previous is None or saved.get("version") != previous,
        "at": utc_now(),
    }
    row.applied = [*row.applied, entry][-APPLIED_KEPT:]
    # From now on the draft changes the saved network.
    row.source = {
        "networkId": saved["id"],
        "name": saved.get("name") or "",
        "purpose": "change",
        "version": saved.get("version"),
        "revision": saved.get("revision"),
        "hidden": source.get("hidden") or {},
        "loadedAt": utc_now(),
        "base": _base_of(saved),
    }
    row.ids = {ref: node_id for ref, node_id in compiled.ids.items() if any(n["id"] == node_id for n in saved.get("nodes") or [])}
    row.proposal = None
    row.updated_at = utc_now()
    active_set = False
    if set_active and _running_id() is None:
        set_active_network(saved["id"])
        active_set = True
    refs = {node_id: ref for ref, node_id in compiled.ids.items()}
    added = _prompts_to_library(saved, refs) if prompts_to_library else 0
    store.save_session(row)
    return {**entry, "activeSet": active_set, "promptsAdded": added}


def undo_entry(row: store.ArchitectSessionRow) -> dict[str, Any] | None:
    """The last application, if it changed an existing network and is not undone yet.

    Only the last one: an older one no longer matches the network's revision.
    """
    entry = row.applied[-1] if row.applied else None
    if not entry or entry.get("undone") or entry.get("mode") != "update":
        return None
    return entry if entry.get("changed") and entry.get("previousVersion") else None


def undo(row: store.ArchitectSessionRow) -> dict[str, Any]:
    """E-17: the version before the last change comes back as a new version."""
    from app.networks.service import restore_version

    entry = undo_entry(row)
    if entry is None:
        raise AppError("architect.undo.nothing", status_code=400)
    restored = restore_version(str(entry["networkId"]), int(entry["previousVersion"]), base_revision=entry.get("revision"))
    entry["undone"] = True
    entry["undoneAs"] = restored.get("version")
    source = row.source or {}
    if source.get("networkId") == entry["networkId"]:
        row.source = {
            **source,
            "version": restored.get("version"),
            "revision": restored.get("revision"),
            "base": _base_of(restored),
            "loadedAt": utc_now(),
        }
    row.updated_at = utc_now()
    store.save_session(row)
    return {"networkId": entry["networkId"], "version": restored.get("version"), "restoredFrom": entry["previousVersion"]}
