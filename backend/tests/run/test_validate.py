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
