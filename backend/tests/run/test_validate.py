from __future__ import annotations

from app.run.graph_models import AgentNetworkDocument
from app.run.validate import validate_document
from tests.run.conftest import mini_doc


def test_two_chat_inputs() -> None:
    raw = mini_doc()
    raw["nodes"].append(
        {"id": "in2", "type": "chat_input", "position": {"x": 0, "y": 0}, "data": {}}
    )
    errors = validate_document(AgentNetworkDocument.model_validate(raw), data_dir="C:/data")
    assert any(e.message_key == "graph.chatInput.duplicate" for e in errors)


def _orchestrator_doc() -> dict:
    raw = mini_doc(requireInput=True)
    raw["nodes"] = [
        node for node in raw["nodes"] if node["id"] != "ag"
    ] + [
        {"id": "orch", "type": "orchestrator", "position": {"x": 0, "y": 0}, "data": {"systemPrompt": "leite"}},
        {"id": "ag", "type": "agent", "position": {"x": 0, "y": 0}, "data": {"displayName": "Schreiber", "systemPrompt": "sys"}},
    ]
    raw["edges"] = [
        {"id": "e1", "source": "in", "sourceHandle": "message", "target": "orch", "targetHandle": "message"},
        {"id": "e2", "source": "llm", "sourceHandle": "llm", "target": "orch", "targetHandle": "llm"},
        {"id": "e3", "source": "llm", "sourceHandle": "llm", "target": "ag", "targetHandle": "llm"},
        {"id": "e4", "source": "orch", "sourceHandle": "channel:ag", "target": "ag", "targetHandle": "channel"},
        {"id": "e5", "source": "orch", "sourceHandle": "message", "target": "end", "targetHandle": "message"},
    ]
    return raw


def test_orchestrator_requires_chat_llm_and_end() -> None:
    raw = _orchestrator_doc()
    raw["edges"] = [edge for edge in raw["edges"] if edge["id"] != "e5"]
    errors = validate_document(AgentNetworkDocument.model_validate(raw), data_dir="C:/data")
    assert any(e.message_key == "graph.orchestrator.noEnd" for e in errors)


def test_orchestrator_graph_is_valid() -> None:
    errors = validate_document(AgentNetworkDocument.model_validate(_orchestrator_doc()), data_dir="C:/data")
    assert errors == []


def test_legacy_orchestrator_message_edge_is_a_channel() -> None:
    from app.run.compile import compile_document

    raw = _orchestrator_doc()
    for edge in raw["edges"]:
        if edge["id"] == "e4":
            edge["sourceHandle"] = "message"
            edge["targetHandle"] = "message"
    doc = AgentNetworkDocument.model_validate(raw)
    assert validate_document(doc, data_dir="C:/data") == []
    compiled = compile_document(doc, network_id="n", network_name="mini")
    assert compiled.orchestrator is not None
    assert compiled.orchestrator.agents == ["ag"]
    assert compiled.orchestrator.finals == ["end"]


def test_orchestrator_agent_is_not_also_a_chain() -> None:
    raw = _orchestrator_doc()
    raw["edges"].append(
        {
            "id": "e6",
            "source": "ag",
            "sourceHandle": "message",
            "target": "end",
            "targetHandle": "message",
        }
    )
    errors = validate_document(AgentNetworkDocument.model_validate(raw), data_dir="C:/data")
    assert any(e.message_key == "graph.agent.mode" for e in errors)


def test_orchestrator_requires_a_channel_on_every_agent() -> None:
    raw = _orchestrator_doc()
    raw["nodes"].append(
        {"id": "loose", "type": "agent", "position": {"x": 0, "y": 0}, "data": {"systemPrompt": "sys"}}
    )
    raw["edges"].append(
        {"id": "e6", "source": "llm", "sourceHandle": "llm", "target": "loose", "targetHandle": "llm"}
    )
    errors = validate_document(AgentNetworkDocument.model_validate(raw), data_dir="C:/data")
    assert any(e.message_key == "graph.orchestrator.looseAgent" for e in errors)


def test_cycle() -> None:
    raw = mini_doc()
    raw["edges"].append(
        {
            "id": "cycle",
            "source": "ag",
            "sourceHandle": "message",
            "target": "in",
            "targetHandle": "message",
        }
    )
    errors = validate_document(AgentNetworkDocument.model_validate(raw), data_dir="C:/data")
    assert any(e.message_key == "graph.cycle" for e in errors)


def test_knowledge_drive_root() -> None:
    raw = mini_doc()
    raw["nodes"].append(
        {
            "id": "kn",
            "type": "knowledge",
            "position": {"x": 0, "y": 0},
            "data": {"sourcePath": r"C:\\"},
        }
    )
    errors = validate_document(AgentNetworkDocument.model_validate(raw), data_dir="C:/data")
    assert any(e.message_key == "graph.knowledge.path" for e in errors)


def test_knowledge_outside_data_dir_ok(tmp_path) -> None:
    folder = tmp_path / "stories"
    folder.mkdir()
    raw = mini_doc()
    raw["nodes"].append(
        {
            "id": "kn",
            "type": "knowledge",
            "position": {"x": 0, "y": 0},
            "data": {"sourcePath": str(folder)},
        }
    )
    errors = validate_document(
        AgentNetworkDocument.model_validate(raw),
        data_dir=str(tmp_path / "data"),
    )
    assert not any(e.message_key == "graph.knowledge.path" for e in errors)
