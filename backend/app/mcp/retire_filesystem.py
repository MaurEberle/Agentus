"""Move stored filesystem MCP nodes onto the built-in file tool."""

from __future__ import annotations

from app.db.engine import utc_now
from app.db.networks import list_networks, upsert_network
from app.db.settings import delete_mcp_server, list_mcp_servers


def retire_filesystem_mcp() -> int:
    servers = [
        row
        for row in list_mcp_servers()
        if isinstance(row, dict) and row.get("recipe_id") == "filesystem"
    ]
    if not servers:
        return 0
    ids = {str(row.get("id") or "") for row in servers}
    changed = 0
    for network in list_networks():
        document = network.document
        nodes = document.get("nodes")
        if not isinstance(nodes, list):
            continue
        touched = False
        for node in nodes:
            if not isinstance(node, dict):
                continue
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            server_id = str(data.get("mcpServerId") or "")
            if server_id not in ids:
                continue
            if node.get("type") != "mcp" and data.get("kind") != "mcp":
                continue
            root = data.get("rootPath")
            name = str(data.get("displayName") or "").strip() or "Dateien"
            node["type"] = "tool"
            node["data"] = {
                "kind": "file_access",
                "displayName": name,
                "rootPath": root,
                "allowWrite": data.get("allowWrite", True),
                "allowDelete": data.get("allowDelete", True),
            }
            touched = True
        if touched:
            network.updated_at = utc_now()
            upsert_network(network)
            changed += 1
    for row in servers:
        server_id = str(row.get("id") or "")
        if server_id:
            delete_mcp_server(server_id)
    return changed
