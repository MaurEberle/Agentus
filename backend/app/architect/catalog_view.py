"""What the architect knows about components: the catalog plus what is set up right now.

The fixed part comes from ``resources/catalog/components.json``; the living part (MCP servers,
built-in tool parameters, guides) is read when asked. Models are not in the catalog; the
architect asks for them with its own tools (entwurf.md, 5.2).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.common.components import catalog_dir, catalog_hash, load_components, node_spec, node_types, tool_kinds

log = logging.getLogger("agentus.architect")

GUIDES = ("linear", "orchestrator", "knowledge", "router")


def mcp_servers() -> list[dict[str, Any]]:
    """Configured MCP servers: id, name, enabled, status, tools. Empty when MCP is missing."""
    try:
        from app.mcp.service import list_servers

        servers = list_servers()
    except Exception:
        log.debug("mcp servers unavailable", exc_info=True)
        return []
    return [
        {
            "id": item.id,
            "name": item.name,
            "enabled": item.enabled,
            "status": item.status,
            "recipe": item.recipe_id,
            "tools": list(item.tool_names or []),
        }
        for item in servers
    ]


def live_catalog() -> dict[str, Any]:
    """The whole catalog for the module page: fixed part, fingerprint, MCP servers."""
    data = dict(load_components())
    data["hash"] = catalog_hash()
    data["mcpServers"] = mcp_servers()
    return data


def overview_lines() -> list[str]:
    """One line per node type and tool kind, for the system prompt."""
    lines = [f"- {spec['type']}: {spec['purpose']}" for spec in node_types()]
    kinds = ", ".join(f"{item['kind']} ({item['purpose']})" for item in tool_kinds())
    lines.append(f"- tool kinds: {kinds}")
    return lines


def _tool_kind_fields(kind: str) -> list[dict[str, Any]]:
    spec = node_spec("tool") or {"fields": []}
    fields = []
    for item in spec["fields"]:
        kinds = item.get("kinds")
        if kinds and kind not in kinds:
            continue
        fields.append({key: value for key, value in item.items() if key != "kinds"})
    return fields


def describe(name: str) -> dict[str, Any] | None:
    """A node type, a tool kind or an MCP server (by id or name), in detail."""
    key = (name or "").strip()
    spec = node_spec(key)
    if spec is not None:
        return {
            "nodeType": spec["type"],
            "purpose": spec["purpose"],
            "use": spec.get("use", ""),
            "fields": [item for item in spec["fields"] if not item.get("advanced")],
            "advancedFields": [item["key"] for item in spec["fields"] if item.get("advanced")],
            "ports": spec.get("ports", []),
            "dynamicOut": spec.get("dynamicOut"),
            "rules": spec.get("rules", []),
            "tips": spec.get("tips", []),
        }
    kind = next((item for item in tool_kinds() if item["kind"] == key), None)
    if kind is not None:
        return {
            "toolKind": kind["kind"],
            "purpose": kind["purpose"],
            "risk": kind.get("risk"),
            "fields": _tool_kind_fields(kind["kind"]),
            "note": "A tool node with this kind; set data.kind to it.",
        }
    lowered = key.lower()
    server = next(
        (item for item in mcp_servers() if item["id"] == key or str(item["name"]).lower() == lowered),
        None,
    )
    if server is not None:
        return {"mcpServer": server, "note": "An mcp node with data.mcpServer set to this name."}
    return None


def guide(pattern: str) -> str | None:
    """A building guide (resources/catalog/guides/<pattern>.md)."""
    name = (pattern or "").strip().lower()
    if name not in GUIDES:
        return None
    folder = catalog_dir()
    if folder is None:
        return None
    path = Path(folder) / "guides" / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
