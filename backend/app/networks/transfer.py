"""Portable network JSON.

One network per file, schemaVersion 1. The file holds name, description, tags,
viewport, nodes, edges, and exportedAt. It has no network id, no runs, and no
knowledge index. Secret values are removed. credentialId may stay; it only
names a local credential.
"""

from __future__ import annotations

from typing import Any, get_args

from pydantic import ValidationError

from app.db.engine import utc_now
from app.http.errors import AppError
from app.run.graph_models import AgentNetworkDocument, NodeType, normalize_mcp_nodes

SCHEMA_VERSION = 1
_NODE_TYPES = set(get_args(NodeType))
_SECRET_FOLDED = frozenset(
    {"secret", "password", "token", "apikey", "authorization", "bearer"}
)
_LOCAL_KEYS = (
    "id",
    "exportedAt",
    "updatedAt",
    "isActive",
    "knowledge",
    "lastRunId",
    "lastUsedAt",
)
_MAX_DEPTH = 8


def _is_secret(key: str) -> bool:
    folded = "".join(ch for ch in key.lower() if ch not in {"_", "-"})
    return folded in _SECRET_FOLDED


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def strip_secrets(value: object, depth: int = 0) -> object:
    """Drop secret keys. Other values are copied."""
    if depth >= _MAX_DEPTH:
        return value
    if isinstance(value, list):
        return [strip_secrets(item, depth + 1) for item in value]
    if isinstance(value, dict):
        cleaned: dict[object, object] = {}
        for key, child in value.items():
            if isinstance(key, str) and _is_secret(key):
                continue
            cleaned[key] = strip_secrets(child, depth + 1)
        return cleaned
    return value


def _reject(key: str) -> None:
    raise AppError(key, status_code=400)


def _check_version(raw: dict[str, Any]) -> None:
    if "schemaVersion" not in raw:
        _reject("networks.import.unreadable")
    version = raw.get("schemaVersion")
    if type(version) is not int or version != SCHEMA_VERSION:
        _reject("networks.import.schema")


def _check_graph(raw: dict[str, Any]) -> None:
    nodes = raw.get("nodes")
    edges = raw.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        _reject("networks.import.unreadable")
    node_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            _reject("networks.import.unreadable")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id or node_id in node_ids:
            _reject("networks.import.unreadable")
        node_ids.add(node_id)
        if node.get("type") not in _NODE_TYPES:
            _reject("networks.import.unreadable")
        position = node.get("position")
        if (
            not isinstance(position, dict)
            or not _number(position.get("x"))
            or not _number(position.get("y"))
        ):
            _reject("networks.import.unreadable")
        data = node.get("data", {})
        if not isinstance(data, dict):
            _reject("networks.import.unreadable")
    edge_ids: set[str] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            _reject("networks.import.unreadable")
        for key in ("id", "source", "target", "sourceHandle", "targetHandle"):
            value = edge.get(key)
            if not isinstance(value, str) or not value:
                _reject("networks.import.unreadable")
        edge_id = str(edge.get("id"))
        if edge_id in edge_ids:
            _reject("networks.import.unreadable")
        edge_ids.add(edge_id)


def to_export(raw: object) -> dict[str, Any]:
    """Return the portable file for a stored or open network document."""
    if not isinstance(raw, dict):
        _reject("networks.import.unreadable")
    _check_version(raw)
    cleaned = strip_secrets(raw)
    if not isinstance(cleaned, dict):
        _reject("networks.import.unreadable")
    portable = dict(cleaned)
    for key in _LOCAL_KEYS:
        portable.pop(key, None)
    _check_graph(portable)
    try:
        doc = normalize_mcp_nodes(AgentNetworkDocument.model_validate(portable))
    except ValidationError as exc:
        raise AppError("networks.import.unreadable", status_code=400) from exc
    payload = doc.model_dump(by_alias=True, exclude_none=True, exclude={"id"})
    payload["schemaVersion"] = SCHEMA_VERSION
    payload["exportedAt"] = utc_now()
    return payload
