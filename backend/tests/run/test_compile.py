from __future__ import annotations

from app.run.compile import compile_document
from app.run.graph_models import AgentNetworkDocument
from tests.run.conftest import mini_doc


def test_compile_agent_without_tools() -> None:
    doc = AgentNetworkDocument.model_validate(mini_doc())
    compiled = compile_document(doc, network_id="n1", network_name="mini")
    assert compiled.agents["ag"].tool_kinds == []
    assert compiled.chat_input is not None
    assert "end" in compiled.end_ids
    assert compiled.agents["ag"].speaks_to_chat is True


def test_speaks_to_chat_follows_message_not_handoff() -> None:
    raw = mini_doc()
    raw["nodes"].extend(
        [
            {
                "id": "llm2",
                "type": "llm",
                "position": {"x": 0, "y": 0},
                "data": {"provider": "ollama", "model": "llama3.2:1b"},
            },
            {
                "id": "ag2",
                "type": "agent",
                "position": {"x": 0, "y": 0},
                "data": {"systemPrompt": "second"},
            },
        ]
    )
    raw["edges"] = [edge for edge in raw["edges"] if edge["id"] != "e3"]
    raw["edges"].extend(
        [
            {
                "id": "e3",
                "source": "ag",
                "sourceHandle": "handoff",
                "target": "ag2",
                "targetHandle": "message",
            },
            {
                "id": "e4",
                "source": "llm2",
                "sourceHandle": "llm",
                "target": "ag2",
                "targetHandle": "llm",
            },
            {
                "id": "e5",
                "source": "ag2",
                "sourceHandle": "message",
                "target": "end",
                "targetHandle": "message",
            },
        ]
    )
    compiled = compile_document(
        AgentNetworkDocument.model_validate(raw), network_id="n1", network_name="mini"
    )
    assert compiled.agents["ag"].speaks_to_chat is False
    assert compiled.agents["ag2"].speaks_to_chat is True


def test_speaks_to_chat_through_router() -> None:
    raw = mini_doc()
    raw["nodes"].append(
        {"id": "rt", "type": "router", "position": {"x": 0, "y": 0}, "data": {}}
    )
    raw["edges"] = [edge for edge in raw["edges"] if edge["id"] != "e3"]
    raw["edges"].extend(
        [
            {
                "id": "e3",
                "source": "ag",
                "sourceHandle": "message",
                "target": "rt",
                "targetHandle": "message",
            },
            {
                "id": "e4",
                "source": "rt",
                "sourceHandle": "default",
                "target": "end",
                "targetHandle": "message",
            },
        ]
    )
    compiled = compile_document(
        AgentNetworkDocument.model_validate(raw), network_id="n1", network_name="mini"
    )
    assert compiled.agents["ag"].speaks_to_chat is True


def test_compile_mcp_node_on_agent() -> None:
    raw = mini_doc()
    raw["nodes"].append(
        {
            "id": "mcp1",
            "type": "mcp",
            "position": {"x": 0, "y": 0},
            "data": {"mcpServerId": "srv-9", "mcpToolNames": ["search"], "credentialId": "cred-gh"},
        }
    )
    raw["edges"].append(
        {
            "id": "em",
            "source": "mcp1",
            "sourceHandle": "tool",
            "target": "ag",
            "targetHandle": "tool",
        }
    )
    compiled = compile_document(
        AgentNetworkDocument.model_validate(raw), network_id="n1", network_name="mini"
    )
    assert compiled.agents["ag"].mcp == [("srv-9", ["search"], "cred-gh")]
    assert compiled.by_id["mcp1"].type == "mcp"


def test_compile_legacy_tool_kind_mcp() -> None:
    raw = mini_doc()
    raw["nodes"].append(
        {
            "id": "mcp1",
            "type": "tool",
            "position": {"x": 0, "y": 0},
            "data": {"kind": "mcp", "mcpServerId": "srv-9"},
        }
    )
    raw["edges"].append(
        {
            "id": "em",
            "source": "mcp1",
            "sourceHandle": "tool",
            "target": "ag",
            "targetHandle": "tool",
        }
    )
    compiled = compile_document(
        AgentNetworkDocument.model_validate(raw), network_id="n1", network_name="mini"
    )
    assert compiled.agents["ag"].mcp == [("srv-9", None, None)]
    assert compiled.by_id["mcp1"].type == "mcp"
