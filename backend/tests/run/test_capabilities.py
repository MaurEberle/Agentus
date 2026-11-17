from app.run.capabilities import capability_text
from app.run.compile import compile_document
from app.run.graph_models import AgentNetworkDocument
from tests.run.conftest import mini_doc


def _doc() -> AgentNetworkDocument:
    raw = mini_doc()
    raw["nodes"].extend(
        [
            {
                "id": "files",
                "type": "tool",
                "position": {"x": 0, "y": 0},
                "data": {
                    "displayName": "Dateisystem",
                    "kind": "file_access",
                    "rootPath": "C:/dev/hello4",
                    "allowWrite": True,
                    "allowDelete": False,
                },
            },
            {
                "id": "term",
                "type": "tool",
                "position": {"x": 0, "y": 0},
                "data": {
                    "displayName": "Terminal",
                    "kind": "terminal",
                    "rootPath": "C:/dev/hello4",
                    "terminalPrograms": ["git", "python", "npm", "node"],
                },
            },
        ]
    )
    raw["edges"].extend(
        [
            {"id": "ef", "source": "files", "sourceHandle": "tool", "target": "ag", "targetHandle": "tool"},
            {"id": "et", "source": "term", "sourceHandle": "tool", "target": "ag", "targetHandle": "tool"},
        ]
    )
    return AgentNetworkDocument.model_validate(raw)


def test_capability_text_lists_root_actions_and_programs() -> None:
    compiled = compile_document(_doc(), network_id="n", network_name="mini")
    text = capability_text(compiled, "ag", available=True)
    assert "Available on this turn" in text
    assert "Dateisystem" in text
    assert "C:/dev/hello4" in text
    assert "write" in text
    assert "Delete: denied" in text
    assert '"action"' in text
    assert "npm" in text
    assert "ls" not in text.split("Programs:", 1)[-1].split(".", 1)[0]
    assert "not in that list is rejected" in text
    withheld = capability_text(compiled, "ag", available=False)
    assert "not available on this turn" in withheld
    assert "C:/dev/hello4" in withheld


def test_mcp_block_names_the_server_root(api_env) -> None:
    """N1: the server row stores root_path; the inventory read rootPath and never showed it."""
    from app.db import init
    from app.db.settings import put_mcp_server

    init()
    put_mcp_server("srv-1", {"name": "Dateien", "enabled": True, "root_path": "C:/data/mcp-root"})
    raw = mini_doc()
    raw["nodes"].append(
        {"id": "m", "type": "mcp", "position": {"x": 0, "y": 0}, "data": {"mcpServerId": "srv-1"}}
    )
    raw["edges"].append({"id": "em", "source": "m", "sourceHandle": "tool", "target": "ag", "targetHandle": "tool"})
    compiled = compile_document(AgentNetworkDocument.model_validate(raw), network_id="n", network_name="mini")
    text = capability_text(compiled, "ag", available=True)
    assert "Root: C:/data/mcp-root." in text
