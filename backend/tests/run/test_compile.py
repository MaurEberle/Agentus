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
