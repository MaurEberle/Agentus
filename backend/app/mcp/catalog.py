from __future__ import annotations

from app.db.settings import list_mcp_servers
from app.mcp.names import openai_tool_name
from app.tools.models import CatalogGroup, CatalogTool


def mcp_catalog_groups() -> list[CatalogGroup]:
    groups: list[CatalogGroup] = []
    for row in list_mcp_servers():
        if not row.get("enabled"):
            continue
        server_id = str(row.get("id") or "")
        tools: list[CatalogTool] = []
        cached = row.get("cached_tools") or []
        if isinstance(cached, list):
            for item in cached:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                mcp_name = str(item["name"])
                schema = item.get("input_schema") or item.get("inputSchema") or {}
                tools.append(
                    CatalogTool(
                        name=openai_tool_name(server_id, mcp_name),
                        kind=None,
                        description=item.get("description"),
                        json_schema=schema if isinstance(schema, dict) else {},
                        server_id=server_id,
                        mcp_tool_name=mcp_name,
                    )
                )
        groups.append(CatalogGroup(id=server_id, tools=tools))
    return groups


def mcp_usage_labels(credential_id: str) -> list[str]:
    labels: list[str] = []
    for row in list_mcp_servers():
        ids = row.get("credential_ids") or []
        if credential_id in ids:
            labels.append(f"mcp:{row.get('name') or row.get('id')}")
    return labels
