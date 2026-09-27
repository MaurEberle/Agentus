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
