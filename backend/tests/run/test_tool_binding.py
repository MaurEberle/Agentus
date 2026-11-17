"""H1: an MCP tool runs only for the node it is wired to, and only if that node allows it."""

from __future__ import annotations

from app.mcp.names import openai_tool_name
from app.run import turn_runtime
from app.run.compile import compile_document
from app.run.graph_models import AgentNetworkDocument

_SERVER_A = "11111111-aaaa-4aaa-8aaa-111111111111"
_SERVER_B = "22222222-bbbb-4bbb-8bbb-222222222222"


def _node(node_id: str, kind: str, data: dict | None = None) -> dict:
    return {"id": node_id, "type": kind, "position": {"x": 0, "y": 0}, "data": data or {}}


def _edge(edge_id: str, source: str, source_handle: str, target: str, target_handle: str) -> dict:
    return {
        "id": edge_id,
        "source": source,
        "sourceHandle": source_handle,
        "target": target,
        "targetHandle": target_handle,
    }


class _FakeMcp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def call(self, server_id: str, tool: str, args: dict) -> dict:
        del args
        self.calls.append((server_id, tool))
        return {"ok": True, "result": "done"}

    def listed_tools(self, server_id: str) -> list:
        del server_id
        return []


def _compiled():
    from app.db import init
    from app.db.settings import put_mcp_server

    init()
    for server_id in (_SERVER_A, _SERVER_B):
        put_mcp_server(
            server_id,
            {
                "id": server_id,
                "name": server_id[:4],
                "enabled": True,
                "transport": "stdio",
                "cached_tools": [
                    {"name": "read_thing", "input_schema": {}},
                    {"name": "delete_thing", "input_schema": {}},
                ],
            },
        )
    doc = AgentNetworkDocument.model_validate(
        {
            "schemaVersion": 1,
            "name": "binding",
            "nodes": [
                _node("in", "chat_input"),
                _node("llm", "llm", {"provider": "ollama", "model": "llama3.2:1b"}),
                _node("ag1", "agent"),
                _node("ag2", "agent"),
                _node("end", "end"),
                # ag1 may only read on server A; server B belongs to ag2.
                _node("mcpA", "mcp", {"mcpServerId": _SERVER_A, "mcpToolNames": ["read_thing"]}),
                _node("mcpB", "mcp", {"mcpServerId": _SERVER_B}),
            ],
            "edges": [
                _edge("1", "in", "message", "ag1", "message"),
                _edge("2", "llm", "llm", "ag1", "llm"),
                _edge("3", "ag1", "message", "ag2", "message"),
                _edge("4", "ag2", "message", "end", "message"),
                _edge("5", "mcpA", "tool", "ag1", "tool"),
                _edge("6", "mcpB", "tool", "ag2", "tool"),
            ],
        }
    )
    return compile_document(doc, network_id="n", network_name="binding")


def _call(compiled, owner_id: str, name: str, fake: _FakeMcp) -> tuple[str, bool]:
    from app.run.controller import get_controller

    ctrl = get_controller()
    ctrl.compiled = compiled
    body, _fact, ok = turn_runtime._dispatch_tool(
        ctrl,
        compiled,
        owner_id=owner_id,
        call_name=name,
        call_arguments="{}",
        tool_kinds=compiled.agents[owner_id].tool_kinds,
        mcp=fake,
        record=None,
        reuse=False,
    )
    return body, ok


def test_allowed_tool_runs(api_env) -> None:
    compiled = _compiled()
    fake = _FakeMcp()
    body, ok = _call(compiled, "ag1", openai_tool_name(_SERVER_A, "read_thing"), fake)
    assert ok is True and body == "done"
    assert fake.calls == [(_SERVER_A, "read_thing")]


def test_tool_outside_the_node_choice_is_refused(api_env) -> None:
    compiled = _compiled()
    fake = _FakeMcp()
    body, ok = _call(compiled, "ag1", openai_tool_name(_SERVER_A, "delete_thing"), fake)
    assert ok is False
    assert "tool.notOffered" in body
    assert fake.calls == []


def test_server_of_another_agent_is_refused(api_env) -> None:
    compiled = _compiled()
    fake = _FakeMcp()
    body, ok = _call(compiled, "ag1", openai_tool_name(_SERVER_B, "delete_thing"), fake)
    assert ok is False
    assert "tool.notOffered" in body
    assert fake.calls == []
    # The agent that owns server B, without a tool choice, may call every tool of it.
    body, ok = _call(compiled, "ag2", openai_tool_name(_SERVER_B, "delete_thing"), fake)
    assert ok is True
    assert fake.calls == [(_SERVER_B, "delete_thing")]


def test_refused_tool_does_not_use_up_max_calls(api_env) -> None:
    from app.run.controller import get_controller

    compiled = _compiled()
    fake = _FakeMcp()
    ctrl = get_controller()
    ctrl.tool_calls = {}
    _call(compiled, "ag1", openai_tool_name(_SERVER_A, "delete_thing"), fake)
    assert ctrl.tool_calls == {}


def _call_with(compiled, owner_id: str, name: str, arguments: str, fake: _FakeMcp) -> tuple[str, bool]:
    from app.run.controller import get_controller

    ctrl = get_controller()
    ctrl.compiled = compiled
    body, _fact, ok = turn_runtime._dispatch_tool(
        ctrl,
        compiled,
        owner_id=owner_id,
        call_name=name,
        call_arguments=arguments,
        tool_kinds=compiled.agents[owner_id].tool_kinds,
        mcp=fake,
        record=None,
        reuse=False,
    )
    return body, ok


def test_broken_argument_json_is_reported_and_not_run(api_env) -> None:
    """N2: broken JSON used to run the tool with {} and an unrelated error."""
    compiled = _compiled()
    fake = _FakeMcp()
    name = openai_tool_name(_SERVER_A, "read_thing")
    body, ok = _call_with(compiled, "ag1", name, '{"path": "a.txt"', fake)
    assert ok is False
    assert "tool.badArguments" in body
    assert "not valid JSON" in body
    assert fake.calls == []
    body, ok = _call_with(compiled, "ag1", name, '["a.txt"]', fake)
    assert ok is False
    assert "one JSON object" in body
    assert fake.calls == []


def test_arguments_sent_as_a_json_string_are_unwrapped(api_env) -> None:
    compiled = _compiled()
    fake = _FakeMcp()
    name = openai_tool_name(_SERVER_A, "read_thing")
    body, ok = _call_with(compiled, "ag1", name, '"{\\"path\\": \\"a.txt\\"}"', fake)
    assert ok is True and body == "done"
    assert fake.calls == [(_SERVER_A, "read_thing")]
    body, ok = _call_with(compiled, "ag1", name, "", fake)
    assert ok is True
