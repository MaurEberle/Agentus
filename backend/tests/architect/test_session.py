"""Model locks, GPU check, idle end and the help chat pause (fix/netz-architekt/entwurf.md, 9)."""

from __future__ import annotations

import json

import pytest

from app.architect import loop
from app.architect import session as sessions
from app.llm.catalog import InstalledModel, InstalledResponse
from app.runtime.models import StreamEvent, ToolCall
from app.settings.models import AppSettingsPatch
from app.settings.service import patch_settings


def _installed(monkeypatch, *items: InstalledModel) -> None:
    monkeypatch.setattr("app.llm.catalog.list_installed", lambda: InstalledResponse(items=list(items)))


def _model(name: str, size: str, *, tools: bool = True, context: int = 65536) -> InstalledModel:
    return InstalledModel(name=name, parameter_size=size, tools=tools, context_length=context)


def _gpu(monkeypatch, *, fits: bool, can_force: bool = True, running: bool = False) -> None:
    check = sessions.GpuCheck(
        need_bytes=10, free_vram_bytes=5 if not fits else 20, free_ram_bytes=50, fits=fits, can_force=can_force, network_running=running
    )
    monkeypatch.setattr(sessions, "check_gpu", lambda model, ctx: check)


def test_model_locks(client, monkeypatch) -> None:
    _installed(
        monkeypatch,
        _model("big:27b", "27.0B"),
        _model("mid:8b", "8.0B", context=8192),
        _model("tiny:2b", "2.0B"),
        _model("mute:14b", "14.0B", tools=False),
    )
    assert sessions.check_model("ollama", "big:27b", None).ok
    mid = sessions.check_model("ollama", "mid:8b", None)
    assert mid.ok and set(mid.warnings) == {"architect.model.small", "architect.model.shortContext"}
    assert sessions.check_model("ollama", "tiny:2b", None).reasons == ["architect.model.tooSmall"]
    assert sessions.check_model("ollama", "mute:14b", None).reasons == ["architect.model.noTools"]
    assert sessions.check_model("ollama", "absent:7b", None).reasons == ["architect.model.notInstalled"]
    assert sessions.check_model("anthropic", "claude", None).reasons == ["architect.model.noCredential"]
    assert sessions.check_model("anthropic", "claude", "cred").ok


def test_start_checks_the_gpu_and_allows_a_slow_start(client, monkeypatch) -> None:
    _installed(monkeypatch, _model("big:27b", "27.0B"))
    row = sessions.create("ollama", "big:27b", None)
    _gpu(monkeypatch, fits=False)
    response = client.post(f"/api/architect/sessions/{row.id}/start", json={})
    assert response.status_code == 409 and response.json()["messageKey"] == "architect.gpu.short"
    assert response.json()["gpu"]["canForce"] is True
    started = client.post(f"/api/architect/sessions/{row.id}/start", json={"forceSlow": True})
    assert started.status_code == 200 and started.json()["slow"] is True
    sessions.stop(row.id)
    _gpu(monkeypatch, fits=False, can_force=False)
    blocked = client.post(f"/api/architect/sessions/{row.id}/start", json={"forceSlow": True})
    assert blocked.json()["messageKey"] == "architect.gpu.tooLarge"


def test_running_network_needs_confirmation(client, monkeypatch) -> None:
    _installed(monkeypatch, _model("big:27b", "27.0B"))
    row = sessions.create("ollama", "big:27b", None)
    _gpu(monkeypatch, fits=True, running=True)
    assert client.post(f"/api/architect/sessions/{row.id}/start", json={}).json()["messageKey"] == "architect.networkRunning"
    assert client.post(f"/api/architect/sessions/{row.id}/start", json={"confirmRunning": True}).status_code == 200


def test_help_chat_pauses_only_when_both_are_local(client, monkeypatch) -> None:
    _installed(monkeypatch, _model("big:27b", "27.0B"))
    _gpu(monkeypatch, fits=True)
    patch_settings(AppSettingsPatch(help_chat={"provider": "ollama", "model": "helper:4b"}))
    local = sessions.create("ollama", "big:27b", None)
    client.post(f"/api/architect/sessions/{local.id}/start", json={})
    assert client.get("/api/help-chat/status").json()["pausedByArchitect"] is True
    sent = client.post("/api/help-chat/messages", json={"text": "Hallo"})
    assert sent.status_code == 409 and sent.json()["messageKey"] == "help.pausedByArchitect"
    client.post(f"/api/architect/sessions/{local.id}/stop")
    assert client.get("/api/help-chat/status").json()["pausedByArchitect"] is False
    cloud = sessions.create("anthropic", "claude", "cred")
    client.post(f"/api/architect/sessions/{cloud.id}/start", json={})
    assert client.get("/api/architect/status").json()["helpPaused"] is False


def test_idle_session_ends_but_keeps_its_chat(client, monkeypatch) -> None:
    row = sessions.create("anthropic", "claude", "cred")
    sessions.start(row.id)
    current = sessions.active()
    assert current is not None
    assert sessions.end_idle(now=current.last_input + sessions.IDLE_SECONDS - 1) is False
    current.generating = True
    assert sessions.end_idle(now=current.last_input + sessions.IDLE_SECONDS + 1) is False
    current.generating = False
    assert sessions.end_idle(now=current.last_input + sessions.IDLE_SECONDS + 1) is True
    assert sessions.active() is None
    assert client.get(f"/api/architect/sessions/{row.id}").json()["state"] == "ended"


DRAFT = {
    "name": "Kette",
    "nodes": [
        {"ref": "chat", "type": "chat_input"},
        {"ref": "writer", "type": "agent", "data": {"displayName": "Schreiber", "systemPrompt": "Schreibe."}},
        {"ref": "model", "type": "llm", "data": {"provider": "ollama", "model": "qwen3:14b"}},
        {"ref": "end", "type": "end"},
    ],
    "links": [["chat", "writer"], ["model", "writer"], ["writer", "end"]],
}


def _events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        name = next((line[7:] for line in block.splitlines() if line.startswith("event: ")), "")
        data = next((line[6:] for line in block.splitlines() if line.startswith("data: ")), "{}")
        out.append((name, json.loads(data)))
    return out


def test_a_turn_runs_tools_streams_and_stores(client, monkeypatch) -> None:
    seen = []

    def fake(req, *, should_abort):
        seen.append(req)
        if len(seen) == 1:
            yield StreamEvent(kind="delta", text="Ich baue den Entwurf. ")
            yield StreamEvent(kind="done", tool_calls=[ToolCall(id="c1", name="draft_set", arguments=json.dumps({"draft": DRAFT}))])
        else:
            yield StreamEvent(kind="delta", text="<think>prüfen</think>Fertig.")
            yield StreamEvent(kind="done")

    loop.set_streamer(fake)
    row = sessions.create("anthropic", "claude", "cred")
    client.post(f"/api/architect/sessions/{row.id}/start", json={})
    response = client.post(f"/api/architect/sessions/{row.id}/messages", json={"text": "Baue eine Kette", "locale": "de"})
    events = _events(response.text)
    names = [name for name, _ in events]
    assert names[:2] == ["delta", "tool"] and "state" in names and names[-1] == "done"
    state = next(payload for name, payload in events if name == "state")
    assert state["check"]["ok"] is True and state["document"]["name"] == "Kette"
    # The step after the tool calls starts a new paragraph.
    assert "".join(p["chunk"] for n, p in events if n == "delta") == "Ich baue den Entwurf. \n\nFertig."
    assert seen[0].tools and "Architect of Agentus Network" in seen[0].messages[0].content
    assert "Answer in German" in seen[0].messages[0].content
    detail = client.get(f"/api/architect/sessions/{row.id}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["tools"][0]["name"] == "draft_set"
    assert detail["title"] == "Baue eine Kette" and detail["check"]["ok"] is True
    exported = client.get(f"/api/architect/sessions/{row.id}/export").json()["markdown"]
    assert "## Entwurf" in exported and "Baue eine Kette" in exported


def test_sending_needs_a_started_session(client) -> None:
    row = sessions.create("anthropic", "claude", "cred")
    response = client.post(f"/api/architect/sessions/{row.id}/messages", json={"text": "Hallo"})
    assert response.status_code == 409 and response.json()["messageKey"] == "architect.notActive"


@pytest.mark.parametrize("limit", [5])
def test_tool_budget_ends_the_turn(client, monkeypatch, limit) -> None:
    patch_settings(AppSettingsPatch(architect={"toolCallsPerAnswer": limit}))
    calls = []

    def fake(req, *, should_abort):
        calls.append(req)
        if req.tools:
            yield StreamEvent(kind="done", tool_calls=[ToolCall(id=f"c{len(calls)}", name="list_components", arguments="{}")])
        else:
            yield StreamEvent(kind="delta", text="Genug.")
            yield StreamEvent(kind="done")

    loop.set_streamer(fake)
    row = sessions.create("anthropic", "claude", "cred")
    client.post(f"/api/architect/sessions/{row.id}/start", json={})
    events = _events(client.post(f"/api/architect/sessions/{row.id}/messages", json={"text": "x"}).text)
    assert sum(1 for name, p in events if name == "tool" and p["status"] == "done") == limit
    assert calls[-1].tools is None and events[-1][0] == "done"


def test_a_chat_can_exist_before_a_model_is_picked(client, monkeypatch) -> None:
    """A network can be read into an empty chat; the start brings the model."""
    _installed(monkeypatch, _model("big:27b", "27.0B"))
    _gpu(monkeypatch, fits=True)
    created = client.post("/api/architect/sessions", json={"provider": "ollama"})
    assert created.status_code == 201 and created.json()["model"] == ""
    assert client.post("/api/architect/sessions", json={"provider": "nope"}).status_code == 400
    session_id = created.json()["id"]
    started = client.post(f"/api/architect/sessions/{session_id}/start", json={"provider": "ollama", "model": "big:27b"})
    assert started.status_code == 200 and started.json()["session"]["model"] == "big:27b"


def test_a_new_chat_on_the_same_local_model_keeps_it_loaded(client, monkeypatch) -> None:
    _installed(monkeypatch, _model("big:27b", "27.0B"), _model("other:14b", "14.0B"))
    _gpu(monkeypatch, fits=True)
    unloaded: list[str] = []
    monkeypatch.setattr("app.runtime.ollama.unload", lambda model, **kwargs: unloaded.append(model))
    first = sessions.create("ollama", "big:27b", None)
    second = sessions.create("ollama", "big:27b", None)
    third = sessions.create("ollama", "other:14b", None)
    sessions.start(first.id)
    sessions.start(second.id)
    # The help chat model may be paused; the architect model stays.
    assert "big:27b" not in unloaded and sessions.active().session_id == second.id
    assert client.get(f"/api/architect/sessions/{first.id}").json()["state"] == "ended"
    sessions.start(third.id)
    assert "big:27b" in unloaded
    sessions.stop(third.id)


def test_brief_edits_wait_for_a_streaming_turn(client) -> None:
    row = sessions.create("anthropic", "claude", "cred")
    sessions.start(row.id)
    current = sessions.active()
    current.generating = True
    busy = client.patch(f"/api/architect/sessions/{row.id}", json={"brief": {"goal": "Texte"}})
    assert busy.status_code == 409 and busy.json()["messageKey"] == "architect.busy"
    current.generating = False
    saved = client.patch(f"/api/architect/sessions/{row.id}", json={"brief": {"goal": "Texte"}})
    assert saved.status_code == 200 and saved.json()["brief"] == {"goal": "Texte"}
    sessions.stop(row.id)


def test_the_session_list_carries_what_the_hover_card_shows(client) -> None:
    from app.architect.session import utc_now
    from app.db import architect as store

    row = sessions.create("anthropic", "claude", "cred")
    row.title = "Geschichten"
    row.brief = {"goal": "Kindergeschichten im Stil von Wilhelm Busch"}
    row.draft = {"name": "Max und Moritz", "nodes": [{"ref": "a"}, {"ref": "b"}], "links": []}
    row.source = {"networkId": "net-1", "name": "Vorlage", "purpose": "template", "version": 3, "base": {}}
    row.applied = [{"networkId": "net-2", "name": "Max und Moritz", "mode": "create", "version": 1, "revision": 1}]
    store.save_session(row)
    for index, role in enumerate(("user", "assistant", "user")):
        store.insert_message(store.ArchitectMessageRow(id=f"m{index}", session_id=row.id, role=role, content="x", created_at=utc_now()))
    empty = sessions.create("ollama", "", None)

    items = {item["id"]: item for item in client.get("/api/architect/sessions").json()["items"]}
    full = items[row.id]
    assert full["messageCount"] == 3
    assert full["goal"] == "Kindergeschichten im Stil von Wilhelm Busch"
    assert (full["draftName"], full["draftNodes"]) == ("Max und Moritz", 2)
    assert full["readIn"] == {"name": "Vorlage", "purpose": "template", "version": 3}
    assert full["lastApplied"] == {"name": "Max und Moritz", "mode": "create", "version": 1, "undone": False}
    bare = items[empty.id]
    assert bare["messageCount"] == 0 and bare["goal"] is None and bare["draftName"] is None
    assert bare["readIn"] is None and bare["lastApplied"] is None
