from __future__ import annotations

import asyncio

from pydantic import BaseModel

from app.db import init
from app.db.vault import put
from app.mcp.models import McpServerCreate, McpToolInfo
from app.mcp.service import create_server, ping_server, set_enabled
from app.mcp.sessions import SESSIONS
from tests.mcp.fakes import FakeSession


class _NeedType(BaseModel):
    type: str


def test_empty_github_schema_gets_recipe_overlay() -> None:
    from app.mcp.recipe_loader import get_recipe
    from app.mcp.sessions import apply_recipe_tool_schemas, tools_from_list_payload

    tools = tools_from_list_payload(
        {
            "tools": [
                {
                    "name": "search_repositories",
                    "description": "Search for GitHub repositories",
                    "inputSchema": {"$schema": "http://json-schema.org/draft-07/schema#"},
                }
            ]
        }
    )
    assert tools[0].input_schema.get("properties") == {}
    recipe = get_recipe("github")
    overlaid = apply_recipe_tool_schemas(tools, recipe)
    props = overlaid[0].input_schema["properties"]
    assert "query" in props
    assert overlaid[0].input_schema.get("required") == ["query"]


def test_empty_filesystem_schema_gets_recipe_overlay() -> None:
    from app.mcp.recipe_loader import get_recipe
    from app.mcp.sessions import apply_recipe_tool_schemas, tools_from_list_payload

    tools = tools_from_list_payload(
        {
            "tools": [
                {
                    "name": "list_directory",
                    "description": "list",
                    "inputSchema": {
                        "$schema": "http://json-schema.org/draft-07/schema#",
                        "type": "object",
                        "properties": {},
                    },
                }
            ]
        }
    )
    recipe = get_recipe("filesystem")
    overlaid = apply_recipe_tool_schemas(tools, recipe)
    assert overlaid[0].input_schema["properties"]["path"]["type"] == "string"
    assert overlaid[0].input_schema.get("required") == ["path"]


def test_default_filesystem_arguments_fills_path() -> None:
    from app.mcp.sessions import default_filesystem_arguments

    filled = default_filesystem_arguments("list_directory", {})
    assert filled["path"] == "."
    kept = default_filesystem_arguments("list_directory", {"path": "sub"})
    assert kept["path"] == "sub"


def test_annotate_github_login_mentions_user(monkeypatch) -> None:
    from app.mcp.models import McpToolInfo
    from app.mcp.sessions import annotate_github_login

    class _Resp:
        def read(self) -> bytes:
            return b'{"login":"octo"}'

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    tools = annotate_github_login(
        [
            McpToolInfo(
                name="search_repositories",
                description="Search for GitHub repositories",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "q"}},
                },
            )
        ],
        "token",
    )
    assert "user:octo" in (tools[0].description or "")
    assert "user:octo" in tools[0].input_schema["properties"]["query"]["description"]


def test_inline_ref_schema() -> None:
    from app.mcp.sessions import repair_input_schema

    repaired = repair_input_schema(
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$ref": "#/definitions/Search",
            "definitions": {
                "Search": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                }
            },
        }
    )
    assert repaired["properties"]["query"]["type"] == "string"
    assert repaired["type"] == "object"


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


def test_recipe_command_not_stale_row(api_env, monkeypatch, tmp_path) -> None:
    init()
    captured: dict = {}

    def _connect(**kwargs: object):
        captured.update(kwargs)
        return FakeSession()

    monkeypatch.setattr("app.mcp.sessions.connect_transport", _connect)
    monkeypatch.setattr("app.mcp.sessions.runtime_available", lambda runtime: True)
    folder = tmp_path / "xlsx"
    folder.mkdir()
    item = create_server(McpServerCreate(recipe_id="excel", enabled=True))
    from app.db.settings import get_mcp_server, put_mcp_server

    row = dict(get_mcp_server(item.id))
    row["command"] = "uvx"
    row["args"] = ["excel-mcp-server", "stdio"]
    put_mcp_server(item.id, row)
    SESSIONS.open_for([item.id], root_overrides={item.id: str(folder)})
    assert captured.get("command")
    assert "uvx" not in str(captured.get("command"))
    assert "@negokaz/excel-mcp-server" in captured.get("args", [])
    SESSIONS.close_all()


def test_open_for_uses_root_override(api_env, monkeypatch, tmp_path) -> None:
    init()
    captured: dict = {}

    def _connect(**kwargs: object):
        captured.update(kwargs)
        return FakeSession()

    monkeypatch.setattr("app.mcp.sessions.connect_transport", _connect)
    monkeypatch.setattr("app.mcp.sessions.runtime_available", lambda runtime: True)
    folder = tmp_path / "kb"
    folder.mkdir()
    item = create_server(McpServerCreate(recipe_id="filesystem", enabled=True))
    SESSIONS.open_for([item.id], root_overrides={item.id: str(folder)})
    assert any(str(folder) in str(arg) for arg in captured.get("args", []))
    SESSIONS.close_all()


def test_call_without_open(api_env) -> None:
    init()
    out = SESSIONS.call("missing", "search", {})
    assert out["ok"] is False
    assert out["errorKey"] == "mcp.session.closed"


def test_call_reopens_after_idle(api_env, monkeypatch, tmp_path) -> None:
    init()
    sessions: list[FakeSession] = []
    folder = tmp_path / "kb"
    folder.mkdir()

    def _connect(**kwargs: object) -> FakeSession:
        fake = FakeSession()
        sessions.append(fake)
        return fake

    monkeypatch.setattr("app.mcp.sessions.connect_transport", _connect)
    monkeypatch.setattr("app.mcp.sessions.runtime_available", lambda runtime: True)
    item = create_server(McpServerCreate(recipe_id="filesystem", enabled=True))
    SESSIONS.open_for([item.id], root_overrides={item.id: str(folder)})
    assert len(sessions) == 1
    SESSIONS._idle_close(item.id)
    assert sessions[0].closed is True
    out = SESSIONS.call(item.id, "search", {"q": "x"})
    assert out["ok"] is True
    assert len(sessions) == 2
    assert sessions[1].calls == [("search", {"q": "x"})]
    SESSIONS.close_all()


def test_idle_reopen_keeps_root_override(api_env, monkeypatch, tmp_path) -> None:
    init()
    captured: list[dict] = []

    def _connect(**kwargs: object) -> FakeSession:
        captured.append(dict(kwargs))
        return FakeSession()

    monkeypatch.setattr("app.mcp.sessions.connect_transport", _connect)
    monkeypatch.setattr("app.mcp.sessions.runtime_available", lambda runtime: True)
    folder = tmp_path / "kb"
    folder.mkdir()
    item = create_server(McpServerCreate(recipe_id="filesystem", enabled=True))
    SESSIONS.open_for([item.id], root_overrides={item.id: str(folder)})
    SESSIONS._idle_close(item.id)
    out = SESSIONS.call(item.id, "list_directory", {})
    assert out["ok"] is True
    assert len(captured) == 2
    assert any(str(folder) in str(arg) for arg in captured[1].get("args", []))
    SESSIONS.close_all()


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


def test_github_open_uses_official_binary(api_env, monkeypatch) -> None:
    init()
    captured: dict = {}

    def _connect(**kwargs: object) -> FakeSession:
        captured.update(kwargs)
        return FakeSession()

    monkeypatch.setattr("app.mcp.sessions.connect_transport", _connect)
    monkeypatch.setattr("app.mcp.sessions.runtime_available", lambda runtime: True)
    item = create_server(
        McpServerCreate(recipe_id="github", credential_ids=["cred-1"], enabled=False)
    )
    set_enabled(item.id, True)
    SESSIONS.open_for([item.id])
    command = str(captured.get("command") or "")
    assert command.endswith("github-mcp-server.exe")
    assert captured.get("args") == ["stdio"]
    assert "npx" not in command
    assert "@modelcontextprotocol/server-github" not in str(captured.get("args"))
    SESSIONS.close_all()


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


def test_github_call_result_parses_text_json() -> None:
    from app.mcp.sessions import call_result_from_payload

    out = call_result_from_payload(
        {
            "content": [
                {
                    "type": "text",
                    "text": '{"total_count": 2, "items": [{"name": "Agentus-Network"}]}',
                }
            ]
        }
    )
    assert out["isError"] is False
    assert out["result"]["total_count"] == 2
    assert out["result"]["items"][0]["name"] == "Agentus-Network"


def test_seed_tool_output_cache_skips_relist() -> None:
    from app.mcp.sessions import seed_tool_output_cache

    class _Session:
        def __init__(self) -> None:
            self._tool_output_schemas: dict = {"already": {"type": "object"}}

    session = _Session()
    seed_tool_output_cache(
        session,
        [
            McpToolInfo(name="already", input_schema={"type": "object"}),
            McpToolInfo(name="search_repositories", input_schema={"type": "object"}),
        ],
        [{"name": "search_repositories", "inputSchema": {"$schema": "http://json-schema.org/draft-07/schema#"}}],
    )
    assert session._tool_output_schemas["already"] == {"type": "object"}
    assert session._tool_output_schemas["search_repositories"] is None


def test_list_tools_tolerant_seeds_after_schema_error() -> None:
    from app.mcp.sessions import _list_tools_tolerant

    class _Legacy:
        def __init__(self) -> None:
            self._tool_output_schemas: dict = {}
            self._dispatcher = self

        async def list_tools(self) -> None:
            _NeedType.model_validate({})

        async def send_raw_request(self, method: str, params: object, opts: object = None) -> dict:
            assert method == "tools/list"
            return {
                "tools": [
                    {
                        "name": "search_repositories",
                        "inputSchema": {"$schema": "http://json-schema.org/draft-07/schema#"},
                    }
                ]
            }

    session = _Legacy()
    tools = asyncio.run(_list_tools_tolerant(session))
    assert [tool.name for tool in tools] == ["search_repositories"]
    assert tools[0].input_schema["type"] == "object"
    assert "search_repositories" in session._tool_output_schemas


def test_call_tool_uses_raw_jsonrpc_not_sdk_list() -> None:
    from app.mcp.sessions import _call_tool_tolerant

    class _Legacy:
        def __init__(self) -> None:
            self._tool_output_schemas: dict = {}
            self._dispatcher = self
            self.sdk_calls = 0

        async def list_tools(self) -> None:
            raise AssertionError("typed list_tools must not run during call")

        async def call_tool(self, name: str, arguments: dict) -> None:
            self.sdk_calls += 1
            raise AssertionError("typed call_tool must not run when dispatcher exists")

        async def send_raw_request(self, method: str, params: object, opts: object = None) -> dict:
            assert method == "tools/call"
            assert isinstance(params, dict)
            assert params["name"] == "search_repositories"
            assert params["arguments"] == {"query": "Agentus"}
            return {
                "content": [
                    {"type": "text", "text": '{"total_count": 1, "items": [{"name": "agentuse"}]}'}
                ]
            }

    out = asyncio.run(
        _call_tool_tolerant(_Legacy(), "search_repositories", {"query": "Agentus"})
    )
    assert out["isError"] is False
    assert out["result"]["total_count"] == 1
    assert out["result"]["items"][0]["name"] == "agentuse"


def test_call_exception_includes_masked_error(api_env, monkeypatch) -> None:
    init()

    class Boom(FakeSession):
        def call_tool(self, name: str, arguments: dict) -> dict:
            raise RuntimeError("upstream sk-abcdefghij exploded")

    monkeypatch.setattr("app.mcp.sessions.connect_transport", lambda **k: Boom())
    monkeypatch.setattr("app.mcp.sessions.runtime_available", lambda runtime: True)
    item = create_server(
        McpServerCreate(recipe_id="github", credential_ids=["cred-1"], enabled=False)
    )
    set_enabled(item.id, True)
    SESSIONS.open_for([item.id])
    out = SESSIONS.call(item.id, "search", {"query": "x"})
    SESSIONS.close_all()
    assert out["ok"] is False
    assert out["errorKey"] == "mcp.call.failed"
    assert "sk-abcdefghij" not in str(out.get("error"))
    assert "sk-***" in str(out.get("error"))
