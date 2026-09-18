from __future__ import annotations

import uuid
from typing import Any

from app.db.engine import get_bootstrap, utc_now
from app.db.network_rag import drop_node as rag_drop_node
from app.db.networks import (
    NetworkRow,
    delete_network,
    duplicate_network,
    get_network,
    list_networks,
    upsert_network,
)
from app.http.errors import AppError
from app.run.graph_models import AgentNetworkDocument
from app.run.knowledge import index_node, status_for_network
from app.run.validate import validate_document
from app.settings.service import load_settings


def _running_id() -> str | None:
    try:
        from app.run.controller import get_controller

        ctrl = get_controller()
        if ctrl.is_busy():
            return ctrl.network_id
    except Exception:
        return None
    return None


def _item(row: NetworkRow) -> dict[str, Any]:
    doc = AgentNetworkDocument.model_validate(row.document) if row.document else None
    errors = []
    status = "unknown"
    try:
        data_dir = str(get_bootstrap().data_dir)
        if doc:
            errors = [
                e.model_dump(by_alias=True)
                for e in validate_document(doc, data_dir=data_dir)
            ]
            status = "invalid" if errors else "valid"
    except Exception:
        status = "unknown"
    settings = load_settings()
    running = _running_id()
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "tags": row.tags,
        "updatedAt": row.updated_at,
        "lastUsedAt": row.last_used_at,
        "nodeCount": len(doc.nodes) if doc else 0,
        "edgeCount": len(doc.edges) if doc else 0,
        "validationStatus": status,
        "validationErrors": errors or None,
        "isActive": settings.active_network_id == row.id,
        "isRunning": running == row.id,
        "lastRunId": row.last_run_id,
    }


def list_network_items() -> list[dict[str, Any]]:
    return [_item(row) for row in list_networks()]


def get_network_document(network_id: str) -> dict[str, Any]:
    row = get_network(network_id)
    if row is None:
        raise AppError("networks.notFound", status_code=404)
    doc = dict(row.document)
    doc.setdefault("id", row.id)
    doc.setdefault("name", row.name)
    doc["knowledge"] = status_for_network(network_id)
    return doc


def create_network(raw: dict[str, Any]) -> dict[str, Any]:
    network_id = str(uuid.uuid4())
    now = utc_now()
    raw = dict(raw)
    raw["id"] = network_id
    raw["updatedAt"] = now
    raw["schemaVersion"] = raw.get("schemaVersion") or 1
    doc = AgentNetworkDocument.model_validate(raw)
    upsert_network(
        NetworkRow(
            id=network_id,
            name=doc.name or "Untitled",
            description=doc.description,
            tags=list(doc.tags or []),
            document=doc.model_dump(by_alias=True),
            updated_at=now,
            last_used_at=None,
            last_run_id=None,
        )
    )
    return get_network_document(network_id)


def replace_network(network_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    if _running_id() == network_id:
        raise AppError("run.busy", status_code=409)
    existing = get_network(network_id)
    if existing is None:
        raise AppError("networks.notFound", status_code=404)
    raw = dict(raw)
    raw["id"] = network_id
    raw["updatedAt"] = utc_now()
    doc = AgentNetworkDocument.model_validate(raw)
    old_ids = {n.id for n in AgentNetworkDocument.model_validate(existing.document).nodes if n.type == "knowledge"}
    new_ids = {n.id for n in doc.nodes if n.type == "knowledge"}
    for dropped in old_ids - new_ids:
        rag_drop_node(network_id, dropped)
    upsert_network(
        NetworkRow(
            id=network_id,
            name=doc.name or existing.name,
            description=doc.description,
            tags=list(doc.tags or []),
            document=doc.model_dump(by_alias=True),
            updated_at=raw["updatedAt"],
            last_used_at=existing.last_used_at,
            last_run_id=existing.last_run_id,
        )
    )
    return get_network_document(network_id)


def patch_network(network_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    row = get_network(network_id)
    if row is None:
        raise AppError("networks.notFound", status_code=404)
    name = patch.get("name", row.name)
    description = patch.get("description", row.description)
    tags = patch.get("tags", row.tags)
    doc = dict(row.document)
    doc["name"] = name
    if description is not None:
        doc["description"] = description
    if tags is not None:
        doc["tags"] = tags
    upsert_network(
        NetworkRow(
            id=row.id,
            name=name,
            description=description,
            tags=list(tags or []),
            document=doc,
            updated_at=utc_now(),
            last_used_at=row.last_used_at,
            last_run_id=row.last_run_id,
        )
    )
    return _item(get_network(network_id))  # type: ignore[arg-type]


def add_tags(ids: list[str], tags: list[str]) -> list[dict[str, Any]]:
    items = []
    for network_id in ids:
        row = get_network(network_id)
        if row is None:
            continue
        merged = list(row.tags)
        for tag in tags:
            if tag not in merged:
                merged.append(tag)
        items.append(patch_network(network_id, {"tags": merged}))
    return items


def delete_networks(ids: list[str]) -> None:
    running = _running_id()
    if running and running in ids:
        raise AppError("run.busy", status_code=409)
    for network_id in ids:
        row = get_network(network_id)
        if row is None:
            raise AppError("networks.notFound", status_code=404)
        delete_network(network_id)


def duplicate(network_id: str) -> dict[str, Any]:
    src = get_network(network_id)
    if src is None:
        raise AppError("networks.notFound", status_code=404)
    new_id = str(uuid.uuid4())
    duplicate_network(network_id, new_id, f"{src.name} copy")
    return get_network_document(new_id)


def validate_network(network_id: str, document: dict[str, Any] | None = None) -> dict[str, Any]:
    data_dir = str(get_bootstrap().data_dir)
    if document is not None:
        doc = AgentNetworkDocument.model_validate(document)
    else:
        row = get_network(network_id)
        if row is None:
            raise AppError("networks.notFound", status_code=404)
        doc = AgentNetworkDocument.model_validate(row.document)
    errors = validate_document(doc, data_dir=data_dir)
    return {
        "valid": not errors,
        "errors": [e.model_dump(by_alias=True) for e in errors],
    }


def export_network(network_id: str) -> dict[str, Any]:
    row = get_network(network_id)
    if row is None:
        raise AppError("networks.notFound", status_code=404)
    doc = dict(row.document)
    doc["id"] = row.id
    doc["exportedAt"] = utc_now()
    return doc


def import_network(document: dict[str, Any]) -> dict[str, Any]:
    raw = dict(document)
    raw.pop("id", None)
    return create_network(raw)


def reindex_knowledge(network_id: str, node_id: str) -> dict[str, str]:
    row = get_network(network_id)
    if row is None:
        raise AppError("networks.notFound", status_code=404)
    doc = AgentNetworkDocument.model_validate(row.document)
    node = next((n for n in doc.nodes if n.id == node_id), None)
    if node is None:
        raise AppError("networks.notFound", status_code=404)
    data_dir = str(get_bootstrap().data_dir)
    state = index_node(network_id, node, data_dir=data_dir, force=True)
    return {"state": state}
