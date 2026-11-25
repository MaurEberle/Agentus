"""Reading in, closing dialog, applying and undoing (fix/netz-architekt/entwurf.md, 7.3 and 15)."""

from __future__ import annotations

import copy
import json

from app.architect import session as sessions
from app.architect.draft import compile_draft, decompile
from app.architect.loop import available_tools
from app.architect.tools import ToolContext, app_lookup, run_tool
from app.db import architect as store
from app.llm.catalog import InstalledModel, InstalledResponse
from app.networks.diff import diff_documents
from app.settings.models import AppSettingsPatch
from app.settings.service import patch_settings

DRAFT = {
    "name": "Kette",
    "nodes": [
        {"ref": "chat", "type": "chat_input", "data": {"placeholder": "Worum geht es?"}},
        {"ref": "writer", "type": "agent", "data": {"displayName": "Schreiber", "systemPrompt": "Schreibe."}},
        {"ref": "model", "type": "llm", "data": {"provider": "ollama", "model": "qwen3:14b"}},
        {"ref": "end", "type": "end"},
    ],
    "links": [["chat", "writer"], ["model", "writer"], ["writer", "end"]],
}


def _installed(monkeypatch) -> None:
    model = InstalledModel(name="qwen3:14b", parameter_size="14B", tools=True, context_length=65536)
    monkeypatch.setattr("app.llm.catalog.list_installed", lambda: InstalledResponse(items=[model]))


def _network(client, draft: dict | None = None) -> dict:
    compiled = compile_draft(draft or DRAFT, app_lookup())
    response = client.post("/api/networks", json=compiled.document)
    assert response.status_code == 201, response.text
    return response.json()


def _tool(session_id: str, name: str, args: dict):
    ctx = ToolContext(session=store.get_session(session_id), cloud=False, lookup=app_lookup)
    result = run_tool(available_tools(), ctx, name, json.dumps(args))
    store.save_session(ctx.session)
    return result


def _url(session_id: str, tail: str) -> str:
    return f"/api/architect/sessions/{session_id}/{tail}"


def _agent(document: dict) -> dict:
    return next(node for node in document["nodes"] if node["type"] == "agent")


def test_reading_back_and_compiling_again_gives_the_same_document(client, monkeypatch) -> None:
    _installed(monkeypatch)
    stored = _network(client)
    read = decompile(stored, app_lookup())
    assert [node["ref"] for node in read.draft["nodes"]] == ["chat", "Schreiber", "qwen3", "end"]
    again = compile_draft(read.draft, app_lookup(), ids=read.ids, base=read.base)
    assert not again.errors
    expected = {key: value for key, value in stored.items() if key not in {"knowledge", "version", "revision"}}
    assert again.document == expected
    assert diff_documents(stored, again.document)["empty"] is True


def test_change_is_saved_only_on_apply_and_can_be_undone(client, monkeypatch) -> None:
    _installed(monkeypatch)
    stored = _network(client)
    row = sessions.create("ollama", "qwen3:14b", None)
    detail = client.post(_url(row.id, "load"), json={"networkId": stored["id"], "purpose": "change"}).json()
    assert detail["source"]["purpose"] == "change" and "base" not in detail["source"]
    assert detail["diff"]["empty"] is True and detail["networkId"] == stored["id"]

    patched = _tool(row.id, "draft_patch", {"upsertNodes": [{"ref": "Schreiber", "data": {"systemPrompt": "Schreibe kurz."}}]})
    assert patched.ok
    proposed = _tool(row.id, "propose_update", {"summary": "Kürzere Antworten."})
    assert proposed.ok
    assert client.get(f"/api/networks/{stored['id']}").json()["version"] == 1  # a proposal saves nothing

    preview = client.get(_url(row.id, "closing")).json()
    agent_id = _agent(stored)["id"]
    assert preview["mode"] == "update" and preview["summary"] == "Kürzere Antworten."
    assert preview["diff"]["changed"] == [{"id": agent_id, "fields": ["systemPrompt"]}]
    assert preview["target"]["version"] == 1 and preview["changedSince"] is False and preview["canUndo"] is False

    applied = client.post(_url(row.id, "apply"), json={}).json()
    assert (applied["mode"], applied["version"], applied["previousVersion"]) == ("update", 2, 1)
    assert applied["session"]["proposal"] is None and applied["session"]["diff"]["empty"] is True
    saved = client.get(f"/api/networks/{stored['id']}").json()
    assert _agent(saved)["data"]["systemPrompt"] == "Schreibe kurz."
    assert {n["id"]: n["position"] for n in saved["nodes"]} == {n["id"]: n["position"] for n in stored["nodes"]}
    assert [e["id"] for e in saved["edges"]] == [e["id"] for e in stored["edges"]]
    newest = client.get(f"/api/networks/{stored['id']}/versions").json()["items"][0]
    assert (newest["source"], newest["note"]) == ("architect", "Kette")

    undone = client.post(_url(row.id, "undo")).json()
    assert (undone["version"], undone["restoredFrom"]) == (3, 1)
    assert _agent(client.get(f"/api/networks/{stored['id']}").json())["data"]["systemPrompt"] == "Schreibe."
    assert client.post(_url(row.id, "undo")).json()["messageKey"] == "architect.undo.nothing"


def test_conflicts_and_a_running_network_are_refused(client, monkeypatch) -> None:
    _installed(monkeypatch)
    stored = _network(client)
    row = sessions.create("ollama", "qwen3:14b", None)
    client.post(_url(row.id, "load"), json={"networkId": stored["id"], "purpose": "change"})
    _tool(row.id, "draft_patch", {"description": "Vom Architekten"})
    # The editor saves in between.
    other = copy.deepcopy(stored)
    other["description"] = "Im Editor geändert"
    assert client.put(f"/api/networks/{stored['id']}?newVersion=false", json=other).status_code == 200
    assert client.get(_url(row.id, "closing")).json()["changedSince"] is True
    refused = client.post(_url(row.id, "apply"), json={})
    assert refused.status_code == 409 and refused.json()["messageKey"] == "networks.conflict"
    assert client.get(f"/api/networks/{stored['id']}").json()["description"] == "Im Editor geändert"

    monkeypatch.setattr("app.networks.service._running_id", lambda: stored["id"])
    assert client.get(_url(row.id, "closing")).json()["running"] is True
    busy = client.post(_url(row.id, "apply"), json={"force": True})
    assert busy.status_code == 409 and busy.json()["messageKey"] == "run.busy"
    monkeypatch.setattr("app.networks.service._running_id", lambda: None)

    forced = client.post(_url(row.id, "apply"), json={"force": True})
    assert forced.status_code == 200 and forced.json()["version"] == 2
    assert client.get(f"/api/networks/{stored['id']}").json()["description"] == "Vom Architekten"


def test_a_template_becomes_a_new_network(client, monkeypatch) -> None:
    _installed(monkeypatch)
    stored = _network(client)
    row = sessions.create("ollama", "qwen3:14b", None)
    detail = client.post(_url(row.id, "load"), json={"networkId": stored["id"], "purpose": "template"}).json()
    assert detail["diff"] is None and detail["networkId"] is None
    assert not set(detail["ids"].values()) & {node["id"] for node in stored["nodes"]}
    blocked = _tool(row.id, "propose_update", {})
    assert not blocked.ok
    _tool(row.id, "draft_patch", {"name": "Kette 2"})
    applied = client.post(_url(row.id, "apply"), json={}).json()
    assert applied["mode"] == "create" and applied["networkId"] != stored["id"] and applied["version"] == 1
    assert client.get(f"/api/networks/{stored['id']}").json()["name"] == "Kette"
    # Further changes go to the new network.
    assert applied["session"]["source"] == {**applied["session"]["source"], "purpose": "change", "networkId": applied["networkId"]}
    assert client.post(_url(row.id, "undo")).status_code == 400  # creating is not undone here


def test_create_with_prompts_and_active_network(client, monkeypatch) -> None:
    _installed(monkeypatch)
    row = sessions.create("ollama", "qwen3:14b", None)
    assert not _tool(row.id, "propose_create", {}).ok  # no draft yet
    assert _tool(row.id, "draft_set", {"draft": DRAFT}).ok
    assert _tool(row.id, "propose_create", {"summary": "Eine Kette."}).ok
    assert client.get("/api/networks").json()["items"] == []
    first = client.post(_url(row.id, "apply"), json={"setActive": True, "promptsToLibrary": True}).json()
    assert first["activeSet"] is True and first["promptsAdded"] == 1
    assert client.get("/api/settings").json()["activeNetworkId"] == first["networkId"]
    prompts = client.get("/api/prompts").json()["items"]
    assert [item["name"] for item in prompts] == ["Kette – Schreiber"]
    again = client.post(_url(row.id, "apply"), json={"mode": "create", "promptsToLibrary": True}).json()
    assert again["promptsAdded"] == 0 and again["networkId"] != first["networkId"]


def test_load_network_only_asks(client, monkeypatch) -> None:
    _installed(monkeypatch)
    stored = _network(client)
    row = sessions.create("ollama", "qwen3:14b", None)
    asked = _tool(row.id, "load_network", {"id": "kette", "purpose": "change"})
    assert asked.ok and asked.key == "architect.tool.loadAsk"
    session = store.get_session(row.id)
    assert session.proposal == {"kind": "load", "networkId": stored["id"], "name": "Kette", "purpose": "change"}
    assert session.draft is None and session.source is None
    assert not _tool(row.id, "load_network", {"id": "gibt es nicht"}).ok
    dismissed = client.post(_url(row.id, "proposal/dismiss")).json()
    assert dismissed["proposal"] is None


def test_cloud_sessions_do_not_see_folder_paths(client, monkeypatch) -> None:
    _installed(monkeypatch)
    draft = copy.deepcopy(DRAFT)
    draft["nodes"].append({"ref": "docs", "type": "knowledge", "data": {"sourcePath": "D:/Projekte/Handbuch"}})
    draft["links"].append(["docs", "writer"])
    stored = _network(client, draft)
    row = sessions.create("anthropic", "claude", None)
    detail = client.post(_url(row.id, "load"), json={"networkId": stored["id"], "purpose": "change"}).json()
    knowledge = next(node for node in detail["draft"]["nodes"] if node["type"] == "knowledge")
    assert "sourcePath" not in knowledge["data"]
    assert detail["source"]["hidden"] == {knowledge["ref"]: ["sourcePath"]}
    kept = next(node for node in detail["document"]["nodes"] if node["type"] == "knowledge")
    assert kept["data"]["sourcePath"] == "D:/Projekte/Handbuch"

    patch_settings(AppSettingsPatch(architect={"sendPathsToCloud": True}))
    shown = client.post(_url(row.id, "load"), json={"networkId": stored["id"], "purpose": "change"}).json()
    knowledge = next(node for node in shown["draft"]["nodes"] if node["type"] == "knowledge")
    assert knowledge["data"]["sourcePath"] == "D:/Projekte/Handbuch" and shown["source"]["hidden"] == {}


def test_new_nodes_in_a_read_in_network_do_not_overlap(client, monkeypatch) -> None:
    _installed(monkeypatch)
    stored = _network(client)
    row = sessions.create("ollama", "qwen3:14b", None)
    client.post(_url(row.id, "load"), json={"networkId": stored["id"], "purpose": "change"})
    _tool(
        row.id,
        "draft_patch",
        {
            "upsertNodes": [{"ref": "pruefer", "type": "agent", "data": {"displayName": "Prüfer", "systemPrompt": "Prüfe."}}],
            "removeLinks": [["Schreiber", "end"]],
            "addLinks": [["Schreiber", "pruefer"], ["qwen3", "pruefer"], ["pruefer", "end"]],
        },
    )
    detail = client.get(f"/api/architect/sessions/{row.id}").json()
    assert detail["check"]["ok"] is True, detail["check"]
    positions = {node["id"]: node["position"] for node in detail["document"]["nodes"]}
    new_id = detail["ids"]["pruefer"]
    assert detail["diff"]["added"] == [new_id]
    for node_id, position in positions.items():
        if node_id == new_id:
            continue
        assert position == next(n["position"] for n in stored["nodes"] if n["id"] == node_id)
        assert not (abs(position["x"] - positions[new_id]["x"]) < 256 and abs(position["y"] - positions[new_id]["y"]) < 120)
