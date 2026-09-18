from __future__ import annotations

from app.db import init
from app.mcp.names import openai_tool_name, openai_tools_for_server, parse_openai_tool_name
from app.mcp.models import McpServerCreate, McpToolInfo
from app.mcp.service import create_server
from app.db.settings import get_mcp_server, put_mcp_server


def test_openai_tool_name_parse_roundtrip(api_env) -> None:
    init()
    item = create_server(McpServerCreate(recipe_id="github", name="gh"))
    row = get_mcp_server(item.id)
    assert row is not None
    row["cached_tools"] = [{"name": "search_repos", "input_schema": {"type": "object"}}]
    put_mcp_server(item.id, row)
    encoded = openai_tool_name(item.id, "search_repos")
    assert encoded.startswith("mcp__")
    parsed = parse_openai_tool_name(encoded)
    assert parsed == (item.id, "search_repos")
    assert parse_openai_tool_name("http") is None


def test_openai_tools_for_server_shape() -> None:
    tools = openai_tools_for_server(
        "srv",
        [McpToolInfo(name="list", description="d", input_schema={"type": "object"})],
    )
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"].startswith("mcp__")
