from __future__ import annotations

import re

from app.mcp.models import McpToolInfo

PREFIX = "mcp__"
_UNSAFE = re.compile(r"[^A-Za-z0-9_]")


def safe_token(value: str) -> str:
    return _UNSAFE.sub("_", value)


def openai_tool_name(server_id: str, mcp_tool_name: str) -> str:
    return f"{PREFIX}{safe_token(server_id)}__{safe_token(mcp_tool_name)}"


def _lookup_server_id(safe_server: str) -> str | None:
    from app.db.settings import list_mcp_servers

    for row in list_mcp_servers():
        real = str(row.get("id") or "")
        if real and safe_token(real) == safe_server:
            return real
    return None


def _lookup_tool_name(server_id: str, safe_tool: str) -> str:
    from app.db.settings import get_mcp_server

    row = get_mcp_server(server_id) or {}
    cached = row.get("cached_tools") or []
    if isinstance(cached, list):
        for tool in cached:
            if isinstance(tool, dict):
                name = str(tool.get("name") or "")
                if name and safe_token(name) == safe_tool:
                    return name
    return safe_tool


def parse_openai_tool_name(name: str) -> tuple[str, str] | None:
    if not name.startswith(PREFIX):
        return None
    rest = name[len(PREFIX) :]
    if "__" not in rest:
        return None
    safe_server, safe_tool = rest.split("__", 1)
    server_id = _lookup_server_id(safe_server)
    if server_id is None:
        return None
    return server_id, _lookup_tool_name(server_id, safe_tool)


def openai_tools_for_server(server_id: str, tools: list[McpToolInfo]) -> list[dict]:
    out: list[dict] = []
    for tool in tools:
        schema = tool.input_schema or {"type": "object", "properties": {}}
        out.append(
            {
                "type": "function",
                "function": {
                    "name": openai_tool_name(server_id, tool.name),
                    "description": tool.description or tool.name,
                    "parameters": schema,
                },
            }
        )
    return out
