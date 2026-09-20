"""Where a credential id is referenced. MCP slots via hook only."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_mcp_usage_provider: Callable[[str], list[str]] | None = None


def set_mcp_usage_provider(fn: Callable[[str], list[str]] | None) -> None:
    global _mcp_usage_provider
    _mcp_usage_provider = fn


def reset_mcp_usage_provider() -> None:
    set_mcp_usage_provider(None)


def _walk_network_doc(
    value: object, credential_id: str, network_id: str, network_name: str, labels: list[str]
) -> None:
    if isinstance(value, dict):
        cid = value.get("credentialId")
        if isinstance(cid, str) and cid == credential_id:
            labels.append(f"network:{network_id}:{network_name}")
        ids = value.get("credentialIds")
        if isinstance(ids, list) and credential_id in ids:
            labels.append(f"network:{network_id}:{network_name}")
        for nested in value.values():
            _walk_network_doc(nested, credential_id, network_id, network_name, labels)
    elif isinstance(value, list):
        for item in value:
            _walk_network_doc(item, credential_id, network_id, network_name, labels)


def usage_labels(credential_id: str) -> list[str]:
    labels: list[str] = []
    from app.db.settings import get_settings as db_get_settings

    raw = db_get_settings() or {}
    help_chat: dict[str, Any] = {}
    nested = raw.get("helpChat") or raw.get("help_chat")
    if isinstance(nested, dict):
        help_chat = nested
    llm = help_chat.get("credentialId", help_chat.get("credential_id"))
    if isinstance(llm, str) and llm == credential_id:
        labels.append("helpChat.llm")
    embed = help_chat.get("embeddingCredentialId", help_chat.get("embedding_credential_id"))
    if isinstance(embed, str) and embed == credential_id:
        labels.append("helpChat.embedding")
    web = help_chat.get("webSearchCredentialId", help_chat.get("web_search_credential_id"))
    if isinstance(web, str) and web == credential_id:
        labels.append("helpChat.webSearch")

    from app.db.networks import list_networks

    for row in list_networks():
        _walk_network_doc(row.document, credential_id, row.id, row.name, labels)

    if _mcp_usage_provider is not None:
        labels.extend(_mcp_usage_provider(credential_id))
    return labels


def is_in_use(credential_id: str) -> bool:
    return bool(usage_labels(credential_id))
