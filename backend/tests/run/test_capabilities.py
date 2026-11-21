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


def test_tool_summary_names_the_tools_of_an_agent() -> None:
    """Coder_Team run, 2026-11-20: the orchestrator could not tell which agent reads files."""
    from app.run.capabilities import tool_summary

    compiled = compile_document(_doc(), network_id="n", network_name="mini")
    assert tool_summary(compiled, "ag") == (
        "file access (read and change) in C:/dev/hello4, terminal (git, python, npm, node)"
    )
    bare = compile_document(AgentNetworkDocument.model_validate(mini_doc()), network_id="n", network_name="mini")
    assert tool_summary(bare, "ag") == "none"


def test_overview_says_what_is_open_now_and_what_opens_later() -> None:
    from app.run.capabilities import orchestrator_tool_overview

    compiled = compile_document(_doc(), network_id="n", network_name="mini")
    reading = orchestrator_tool_overview(compiled, "ag", ["file_access"])
    assert reading.startswith("Files: you can read files in C:/dev/hello4 yourself (search with text")
    assert "changing them opens only after an agent call failed or during a takeover." in reading
    assert "- Terminal (terminal): runs one allowed program (git, python, npm, node) in C:/dev/hello4; opens only after" in reading
    repair = orchestrator_tool_overview(compiled, "ag", ["file_access", "terminal"])
    assert "in C:/dev/hello4; open now." in repair
    closed = orchestrator_tool_overview(compiled, "ag", [])
    assert closed.startswith("Files: your file access in C:/dev/hello4 is not open on this turn.")


def test_overview_without_file_access_and_with_read_only_files() -> None:
    from app.run.capabilities import orchestrator_tool_overview

    raw = mini_doc()
    raw["nodes"].append(
        {"id": "web", "type": "tool", "position": {"x": 0, "y": 0}, "data": {"displayName": "Websuche", "kind": "web_search"}}
    )
    raw["edges"].append({"id": "ew", "source": "web", "sourceHandle": "tool", "target": "ag", "targetHandle": "tool"})
    compiled = compile_document(AgentNetworkDocument.model_validate(raw), network_id="n", network_name="mini")
    text = orchestrator_tool_overview(compiled, "ag", [])
    assert text.startswith("Files: you have no file access. To read or check a file, call an agent with file access")
    assert "- Websuche (web_search): searches the web and returns titles, links and snippets; opens only after" in text
    raw["nodes"].append(
        {
            "id": "ro",
            "type": "tool",
            "position": {"x": 0, "y": 0},
            "data": {"kind": "file_access", "rootPath": "C:/ro", "allowWrite": False, "allowDelete": False},
        }
    )
    raw["edges"].append({"id": "er", "source": "ro", "sourceHandle": "tool", "target": "ag", "targetHandle": "tool"})
    compiled = compile_document(AgentNetworkDocument.model_validate(raw), network_id="n", network_name="mini")
    text = orchestrator_tool_overview(compiled, "ag", ["file_access"])
    assert text.startswith("Files: you can read files in C:/ro yourself; changing them is switched off.")


def test_overview_names_an_mcp_server(api_env) -> None:
    from app.db import init
    from app.db.settings import put_mcp_server
    from app.run.capabilities import orchestrator_tool_overview, tool_summary

    init()
    put_mcp_server("srv-1", {"name": "Dateien", "enabled": True, "root_path": "C:/data/mcp-root"})
    raw = mini_doc()
    raw["nodes"].append(
        {
            "id": "m",
            "type": "mcp",
            "position": {"x": 0, "y": 0},
            "data": {"mcpServerId": "srv-1", "mcpToolNames": ["read_file", "list_dir"]},
        }
    )
    raw["edges"].append({"id": "em", "source": "m", "sourceHandle": "tool", "target": "ag", "targetHandle": "tool"})
    compiled = compile_document(AgentNetworkDocument.model_validate(raw), network_id="n", network_name="mini")
    text = orchestrator_tool_overview(compiled, "ag", [])
    assert "- Dateien (MCP server): read_file, list_dir; opens only after an agent call failed" in text
    assert tool_summary(compiled, "ag") == "MCP server Dateien"
