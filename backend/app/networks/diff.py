"""What changed between two network documents (fix/netz-versionen/entwurf.md, 10; netz-architekt 7.3).

Nodes are matched by id, edges by their ends and handles. A node whose type or data differ is
"changed" with the differing keys; a node that only moved is "moved", which is no change of content.
"""

from __future__ import annotations

from typing import Any

HEAD_KEYS = ("name", "description", "tags")


def _label(node: dict[str, Any]) -> str:
    data = node.get("data") or {}
    for key in ("displayName", "model", "kind"):
        value = str(data.get(key) or "").strip()
        if value:
            return value
    return str(node.get("type") or "")


def _edge_key(edge: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(edge.get("source") or ""),
        str(edge.get("sourceHandle") or ""),
        str(edge.get("target") or ""),
        str(edge.get("targetHandle") or ""),
    )


def _edge_out(edge: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": edge.get("source"),
        "sourceHandle": edge.get("sourceHandle"),
        "target": edge.get("target"),
        "targetHandle": edge.get("targetHandle"),
    }


def diff_documents(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    """Head fields, added, removed, changed and moved nodes, added and removed edges.

    ``nodes`` names every node that appears in the result (type and label), from either side,
    so a view can show removed nodes too.
    """
    before = before or {}
    after = after or {}
    old = {str(node.get("id")): node for node in before.get("nodes") or []}
    new = {str(node.get("id")): node for node in after.get("nodes") or []}
    added = [node_id for node_id in new if node_id not in old]
    removed = [node_id for node_id in old if node_id not in new]
    changed: list[dict[str, Any]] = []
    moved: list[str] = []
    for node_id, node in new.items():
        prior = old.get(node_id)
        if prior is None:
            continue
        fields: list[str] = []
        if prior.get("type") != node.get("type"):
            fields.append("type")
        old_data = prior.get("data") or {}
        new_data = node.get("data") or {}
        fields += sorted(key for key in set(old_data) | set(new_data) if old_data.get(key) != new_data.get(key))
        if fields:
            changed.append({"id": node_id, "fields": fields})
        elif (prior.get("position") or {}) != (node.get("position") or {}):
            moved.append(node_id)
    old_edges = {_edge_key(edge): edge for edge in before.get("edges") or []}
    new_edges = {_edge_key(edge): edge for edge in after.get("edges") or []}
    edges_added = [_edge_out(edge) for key, edge in new_edges.items() if key not in old_edges]
    edges_removed = [_edge_out(edge) for key, edge in old_edges.items() if key not in new_edges]
    head = [key for key in HEAD_KEYS if (before.get(key) or None) != (after.get(key) or None)]
    named = set(added) | set(removed) | {item["id"] for item in changed} | set(moved)
    for edge in edges_added + edges_removed:
        named.add(str(edge["source"]))
        named.add(str(edge["target"]))
    nodes = {
        node_id: {"type": (new.get(node_id) or old.get(node_id) or {}).get("type"), "label": _label(new.get(node_id) or old.get(node_id) or {})}
        for node_id in named
        if node_id in new or node_id in old
    }
    return {
        "head": head,
        "added": added,
        "removed": removed,
        "changed": changed,
        "moved": moved,
        "edgesAdded": edges_added,
        "edgesRemoved": edges_removed,
        "nodes": nodes,
        "empty": not (head or added or removed or changed or edges_added or edges_removed),
    }
