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


def _credential_refs(value: object, found: set[str]) -> None:
    """Every credentialId / credentialIds entry anywhere in a network document."""
    if isinstance(value, dict):
        cid = value.get("credentialId")
        if isinstance(cid, str) and cid:
            found.add(cid)
        ids = value.get("credentialIds")
        if isinstance(ids, list):
            found.update(item for item in ids if isinstance(item, str))
        for nested in value.values():
            _credential_refs(nested, found)
    elif isinstance(value, list):
        for item in value:
            _credential_refs(item, found)


def usage_index(credential_ids: list[str]) -> dict[str, list[str]]:
    """Usage labels for several credentials; settings and networks are read once (N9)."""
    from app.db.networks import list_networks
    from app.db.settings import get_settings as db_get_settings

    raw = db_get_settings() or {}
    networks: list[tuple[str, str, set[str]]] = []
    for row in list_networks():
        refs: set[str] = set()
        _credential_refs(row.document, refs)
        networks.append((row.id, row.name, refs))
    out: dict[str, list[str]] = {}
    for credential_id in credential_ids:
        labels = _help_chat_labels(raw, credential_id)
        labels.extend(_architect_labels(raw, credential_id))
        labels.extend(f"network:{nid}:{name}" for nid, name, refs in networks if credential_id in refs)
        if _mcp_usage_provider is not None:
            labels.extend(_mcp_usage_provider(credential_id))
        out[credential_id] = list(dict.fromkeys(labels))
    return out


def usage_labels(credential_id: str) -> list[str]:
    return usage_index([credential_id])[credential_id]


def _help_chat_labels(raw: dict[str, Any], credential_id: str) -> list[str]:
    labels: list[str] = []
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
    return labels


def _architect_labels(raw: dict[str, Any], credential_id: str) -> list[str]:
    """The architect's model, examples embedding and web search (fix/netz-architekt/entwurf.md, 13)."""
    architect = raw.get("architect") if isinstance(raw.get("architect"), dict) else {}
    pairs = (("credentialId", "architect.llm"), ("embeddingCredentialId", "architect.embedding"), ("webSearchCredentialId", "architect.webSearch"))
    return [label for key, label in pairs if architect.get(key) == credential_id]


def is_in_use(credential_id: str) -> bool:
    return bool(usage_labels(credential_id))
