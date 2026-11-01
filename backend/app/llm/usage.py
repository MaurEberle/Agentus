"""Where an installed model name is referenced."""

from __future__ import annotations

from typing import Any

from app.db.networks import list_networks
from app.db.settings import get_settings
from app.runtime.ollama import tag_key


def _same(left: object, wanted: str) -> bool:
    return isinstance(left, str) and bool(left.strip()) and tag_key(left) == wanted


def _node_label(node: dict[str, Any]) -> str:
    data = node.get("data")
    if isinstance(data, dict):
        name = data.get("displayName")
        if isinstance(name, str) and name.strip():
            return name.strip()
    kind = node.get("type")
    return str(kind) if isinstance(kind, str) and kind else "node"


def model_usages(name: str) -> list[dict[str, str]]:
    """Graph and help-chat references. A running loaded model is added by the router."""
    wanted = tag_key(name)
    if not wanted:
        return []
    found: list[dict[str, str]] = []
    raw = get_settings() or {}
    help_chat = raw.get("helpChat") or raw.get("help_chat") or {}
    if isinstance(help_chat, dict):
        if _same(help_chat.get("model"), wanted):
            found.append({"kind": "help.llm"})
        if _same(help_chat.get("embeddingModel") or help_chat.get("embedding_model"), wanted):
            found.append({"kind": "help.embed"})
        if _same(help_chat.get("fallbackModel") or help_chat.get("fallback_model"), wanted):
            found.append({"kind": "help.fallback"})
    for row in list_networks():
        nodes = row.document.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if not isinstance(node, dict):
                continue
            data = node.get("data")
            if not isinstance(data, dict):
                continue
            kind = node.get("type")
            hit = False
            if kind == "llm" and _same(data.get("model"), wanted):
                hit = True
            if kind == "knowledge" and _same(data.get("embeddingModel"), wanted):
                hit = True
            if not hit:
                continue
            found.append(
                {
                    "kind": "network",
                    "network": row.name,
                    "node": _node_label(node),
                }
            )
    return found
