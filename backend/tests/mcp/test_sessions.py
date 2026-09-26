from __future__ import annotations

from app.db import init
from app.db.vault import put
from app.mcp.models import McpServerCreate
from app.mcp.service import create_server, ping_server, set_enabled
from app.mcp.sessions import SESSIONS
from tests.mcp.fakes import FakeSession


def test_github_style_schema_without_type_is_repaired() -> None:
    from app.mcp.sessions import tools_from_list_payload

    tools = tools_from_list_payload(
        {
            "tools": [
                {
                    "name": "create_or_update_file",
                    "description": "create",
                    "inputSchema": {
                        "$schema": "http://json-schema.org/draft-07/schema#",
                        "properties": {"path": {"type": "string"}},
                    },
                }
            ]
        }
    )
    assert tools[0].name == "create_or_update_file"
    assert tools[0].input_schema["type"] == "object"
    assert "path" in tools[0].input_schema["properties"]


def test_call_without_open(api_env) -> None:
    init()
    out = SESSIONS.call("missing", "search", {})
    assert out["ok"] is False
    assert out["errorKey"] == "mcp.session.closed"


def test_open_for_and_call_masks(api_env, monkeypatch) -> None:
    init()
    fake = FakeSession(result={"text": "hello sk-abcdefghij"})

    def _connect(**kwargs: object) -> FakeSession:
        return fake

    monkeypatch.setattr("app.mcp.sessions.connect_transport", _connect)
    monkeypatch.setattr("app.mcp.sessions.runtime_available", lambda runtime: True)
    item = create_server(
        McpServerCreate(recipe_id="github", credential_ids=["cred-1"], enabled=False)
    )
    set_enabled(item.id, True)
    SESSIONS.open_for([item.id])
    listed = SESSIONS.listed_tools(item.id)
    assert [tool.name for tool in listed] == ["search"]
    out = SESSIONS.call(item.id, "search", {"q": "x"})
    assert out["ok"] is True
    assert "sk-abcdefghij" not in str(out["result"])
    assert "sk-***" in str(out["result"])
    assert "hello" in str(out["result"])
    SESSIONS.close_all()
    assert fake.closed is True


def test_postgres_app_db_no_spawn(api_env, monkeypatch) -> None:
    init()
    spawned = []

    def _connect(**kwargs: object) -> FakeSession:
        spawned.append(True)
        return FakeSession()

    monkeypatch.setattr("app.mcp.sessions.connect_transport", _connect)
    monkeypatch.setattr("app.mcp.service.runtime_available", lambda runtime: True)
    item = create_server(
        McpServerCreate(recipe_id="postgres", credential_ids=["pg-1"], enabled=True)
    )
    put("pg-1", "file:C:/data/workspace.sqlite")
    from app.http.errors import AppError
    import pytest

    with pytest.raises(AppError) as err:
        ping_server(item.id)
    assert err.value.message_key == "mcp.postgres.appDb"
    assert spawned == []
