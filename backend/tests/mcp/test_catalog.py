from __future__ import annotations

from app.db import init
from app.mcp import register_hooks
from app.mcp.models import McpServerCreate
from app.mcp.service import create_server, set_enabled
from app.tools.catalog import list_catalog_groups
from tests.mcp.fakes import FakeSession
from app.mcp.models import McpToolInfo


def test_ping_populates_catalog_group(api_env, monkeypatch) -> None:
    init()
    register_hooks()
    fake = FakeSession(
        tools=[McpToolInfo(name="search", description="s", input_schema={"type": "object"})]
    )
    monkeypatch.setattr("app.mcp.sessions.connect_transport", lambda **k: fake)
    monkeypatch.setattr("app.mcp.service.runtime_available", lambda runtime: True)
    item = create_server(McpServerCreate(recipe_id="github", enabled=True))
    from app.mcp.service import ping_server

    status, key = ping_server(item.id)
    assert status == "ok"
    assert key is None
    groups = list_catalog_groups()
    mcp_groups = [g for g in groups if g.id == item.id]
    assert len(mcp_groups) == 1
    assert mcp_groups[0].tools[0].server_id == item.id
    assert mcp_groups[0].tools[0].mcp_tool_name == "search"
    assert mcp_groups[0].tools[0].name.startswith("mcp__")


def test_usage_provider(api_env) -> None:
    init()
    register_hooks()
    item = create_server(
        McpServerCreate(recipe_id="github", credential_ids=["cred-1"], enabled=False)
    )
    from app.settings.in_use import usage_labels

    labels = usage_labels("cred-1")
    assert f"mcp:{item.name}" in labels
