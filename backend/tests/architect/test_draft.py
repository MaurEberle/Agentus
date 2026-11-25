"""The draft format and its translation (fix/netz-architekt/entwurf.md, 7)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.architect.draft import Lookup, compile_draft, normalize, patch
from app.run.graph_models import AgentNetworkDocument
from app.run.validate import validate_document

GUIDES = Path(__file__).resolve().parents[3] / "resources" / "catalog" / "guides"


def _validating(tmp_path) -> Lookup:
    def validate(document):
        doc = AgentNetworkDocument.model_validate(document)
        return [(e.node_id, e.message_key) for e in validate_document(doc, data_dir=str(tmp_path))]

    return Lookup(
        credentials=[{"id": "cred-1", "name": "Anthropic privat", "kind": "anthropic"}],
        mcp_servers=[{"id": "mcp-1", "name": "Git", "enabled": True}],
        installed={"qwen3:14b": {"tools": True}, "tiny:1b": {"tools": False}},
        validate=validate,
    )


TEAM = {
    "name": "Recherche-Team",
    "nodes": [
        {"ref": "chat", "type": "chat_input", "data": {"placeholder": "Thema?"}},
        {"ref": "chef", "type": "orchestrator", "data": {"displayName": "Chef", "systemPrompt": "Leite das Team."}},
        {"ref": "model", "type": "llm", "data": {"provider": "anthropic", "model": "claude-x", "credential": "Anthropic privat"}},
        {"ref": "forscher", "type": "agent", "data": {"displayName": "Forscher", "systemPrompt": "Recherchiere."}},
        {"ref": "zeit", "type": "tool", "data": {"kind": "datetime"}},
        {"ref": "ende", "type": "end"},
    ],
    "links": [["chat", "chef"], ["model", "chef"], ["model", "forscher"], ["chef", "forscher"], ["zeit", "forscher"], ["chef", "ende"]],
}


def test_orchestrator_team_compiles_to_a_valid_network(tmp_path) -> None:
    compiled = compile_draft(TEAM, _validating(tmp_path))
    assert compiled.errors == [], [p.text for p in compiled.errors]
    doc = compiled.document
    by_ref = compiled.ids
    channel = next(e for e in doc["edges"] if e["source"] == by_ref["chef"] and e["target"] == by_ref["forscher"])
    assert channel["sourceHandle"] == f"channel:{by_ref['forscher']}" and channel["targetHandle"] == "channel"
    llm = next(n for n in doc["nodes"] if n["id"] == by_ref["model"])
    assert llm["data"]["credentialId"] == "cred-1" and "credential" not in llm["data"]
    chat = next(n for n in doc["nodes"] if n["id"] == by_ref["chat"])
    assert chat["data"]["requireInput"] is False  # initial values come from the catalog
    xs = {ref: next(n["position"]["x"] for n in doc["nodes"] if n["id"] == node_id) for ref, node_id in by_ref.items()}
    assert xs["chat"] < xs["chef"] < xs["forscher"]


def test_ids_stay_stable_across_compiles(tmp_path) -> None:
    first = compile_draft(TEAM, _validating(tmp_path))
    again = compile_draft(TEAM, _validating(tmp_path), ids=first.ids)
    assert again.ids == first.ids


def test_problems_name_the_node_and_the_fix(tmp_path) -> None:
    draft = json.loads(json.dumps(TEAM))
    draft["nodes"][2]["data"]["credential"] = "Unbekannt"
    draft["nodes"][3]["data"]["apiKey"] = "x"
    draft["nodes"][3]["data"]["maxToolCalls"] = 5000
    draft["links"].append(["zeit", "ende"])
    compiled = compile_draft(draft, _validating(tmp_path))
    texts = " | ".join(p.text for p in compiled.errors)
    assert "Unknown credential 'Unbekannt'. Available: Anthropic privat." in texts
    assert "'forscher' (agent) has no field 'apiKey'" in texts
    assert "maxToolCalls must be between 1 and 1000" in texts
    assert "tool cannot connect to end" in texts


def test_validation_errors_come_back_with_the_ref(tmp_path) -> None:
    draft = json.loads(json.dumps(TEAM))
    draft["links"] = [link for link in draft["links"] if link != ["model", "forscher"]]
    compiled = compile_draft(draft, _validating(tmp_path))
    hit = next(p for p in compiled.errors if p.key == "graph.agent.noLlm")
    assert hit.ref == "forscher" and "exactly one LLM edge" in hit.text


def test_router_links_name_their_branch(tmp_path) -> None:
    draft = {
        "name": "Triage",
        "nodes": [
            {"ref": "chat", "type": "chat_input"},
            {"ref": "sort", "type": "router", "data": {"branches": [{"name": "Dringend", "match": "firstLine", "pattern": "URGENT"}]}},
            {"ref": "a", "type": "end"},
            {"ref": "b", "type": "end"},
        ],
        "links": [["chat", "sort"], ["sort", "a", "Dringend"], ["sort", "b", "default"]],
    }
    compiled = compile_draft(draft, _validating(tmp_path))
    assert compiled.errors == [], [p.text for p in compiled.errors]
    handles = {e["sourceHandle"] for e in compiled.document["edges"] if e["source"] == compiled.ids["sort"]}
    assert handles == {"br-dringend", "default"}
    draft["links"][1] = ["sort", "a"]
    missing = compile_draft(draft, _validating(tmp_path))
    assert any("needs a branch name (Dringend) or 'default'" in p.text for p in missing.errors)


def test_hints_for_missing_models_and_risky_tools(tmp_path) -> None:
    draft = {
        "name": "Lokal",
        "nodes": [
            {"ref": "chat", "type": "chat_input"},
            {"ref": "dev", "type": "agent", "data": {"systemPrompt": "x"}},
            {"ref": "small", "type": "llm", "data": {"model": "tiny:1b"}},
            {"ref": "sh", "type": "tool", "data": {"kind": "terminal", "terminalMode": "unrestricted", "rootPath": str(tmp_path)}},
            {"ref": "end", "type": "end"},
        ],
        "links": [["chat", "dev"], ["small", "dev"], ["sh", "dev"], ["dev", "end"]],
    }
    hints = " | ".join(p.text for p in compile_draft(draft, _validating(tmp_path)).hints)
    assert "tiny:1b cannot call tools" in hints and "unrestricted terminal" in hints
    draft["nodes"][2]["data"]["model"] = "missing:7b"
    assert any("not installed" in p.text for p in compile_draft(draft, _validating(tmp_path)).hints)


def test_patch_upserts_removes_and_links() -> None:
    draft, _ = normalize(TEAM)
    changed, problems = patch(
        draft,
        {
            "upsertNodes": [{"ref": "forscher", "data": {"systemPrompt": "Neu", "maxToolCalls": None}}, {"ref": "pruefer", "type": "agent"}],
            "removeNodes": ["zeit"],
            "addLinks": [["chef", "pruefer"], ["model", "pruefer"]],
            "removeLinks": [["chat", "nope"]],
            "name": "Team 2",
        },
    )
    refs = [node["ref"] for node in changed["nodes"]]
    assert "zeit" not in refs and refs[-1] == "pruefer" and changed["name"] == "Team 2"
    assert next(n for n in changed["nodes"] if n["ref"] == "forscher")["data"]["systemPrompt"] == "Neu"
    assert ["zeit", "forscher"] not in changed["links"] and ["chef", "pruefer"] in changed["links"]
    assert any("no such link" in p.text for p in problems)


def test_guide_skeletons_compile_without_shape_errors() -> None:
    for path in sorted(GUIDES.glob("*.md")):
        blocks = re.findall(r"```json\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
        assert blocks, path.name
        for block in blocks:
            compiled = compile_draft(json.loads(block), Lookup())
            assert compiled.errors == [], (path.name, [p.text for p in compiled.errors])
