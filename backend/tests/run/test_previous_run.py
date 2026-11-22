"""Continue from an earlier run (Coder_Team run, 2026-11-20: "check the last work" meant nothing)."""

from __future__ import annotations

import time

import pytest

from app.db.runs import list_logs
from app.runtime.errors import RuntimeApiError
from app.runtime.models import CompletionRequest, CompletionResult

_BRIEFING = "Vorlauf: Karten gebaut, Styles für .language-card fehlen in src/modules/_cards.scss."


def _ok(text: str) -> CompletionResult:
    return CompletionResult(content=text, model="m", finish_reason="stop")


def _is_orch(req: CompletionRequest) -> bool:
    return "You orchestrate" in (req.messages[0].content or "")


def _is_analysis(req: CompletionRequest) -> bool:
    return (req.messages[0].content or "").startswith("You lead an agent network.")


def _blob(req: CompletionRequest) -> str:
    return "\n".join(message.content or "" for message in req.messages)


def _setup() -> None:
    from app.db import init
    from app.db.engine import utc_now
    from app.db.networks import NetworkRow, upsert_network
    from app.settings.models import AppSettingsPatch
    from app.settings.service import patch_settings
    from tests.run.test_validate import _orchestrator_doc

    init()
    upsert_network(
        NetworkRow(
            id="net-1",
            name="mini",
            description=None,
            tags=[],
            document=_orchestrator_doc(),
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    patch_settings(AppSettingsPatch(active_network_id="net-1"))


def _first_run(monkeypatch) -> dict:
    """One agent call, then a final answer."""
    calls = {"orch": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("Karten gebaut. Die Styles fehlen noch.")
        calls["orch"] += 1
        if calls["orch"] > 1:
            return _ok('{"action":"finish","text":"Fertig: Karten gebaut, Styles offen."}')
        return _ok('{"action":"call","agent":"Schreiber","task":"Baue die Sprachkarten."}')

    _setup()
    return _run(monkeypatch, _complete, "Bau eine Hello-World-App mit bunten Karten.")


def _second_run(monkeypatch, complete, previous_run_id: str, text: str = "Mach die Styles fertig.") -> dict:
    return _run(monkeypatch, complete, text, previous_run_id)


def _run(monkeypatch, complete, text: str, previous_run_id: str | None = None) -> dict:
    from app.db.runs import get_run
    from app.run.controller import get_controller

    monkeypatch.setattr("app.runtime.completions.complete_live", complete)
    ctrl = get_controller()
    started = ctrl.start()
    for _ in range(200):
        if ctrl.service_status == "running":
            break
        time.sleep(0.01)
    ctrl.send_chat(text, previous_run_id=previous_run_id)
    assert ctrl.thread is not None
    ctrl.thread.join(timeout=5)
    assert ctrl.thread.is_alive() is False
    stored = get_run(started["runId"])
    assert stored is not None
    return stored


def test_the_orchestrator_reads_the_chosen_run_and_keeps_its_briefing(monkeypatch, api_env) -> None:
    first = _first_run(monkeypatch)
    assert first["outcome"] == "succeeded", first.get("error_message")
    seen: dict = {"agent": []}

    def _complete(req, should_abort=None, on_progress=None):
        if _is_analysis(req):
            seen["record"] = req.messages[1].content or ""
            seen["tools"] = req.tools
            return _ok(_BRIEFING)
        if not _is_orch(req):
            seen["agent"].append(_blob(req))
            return _ok("Styles geschrieben.")
        blob = _blob(req)
        seen.setdefault("orch", blob)
        if "Styles geschrieben" in blob:
            return _ok('{"action":"finish","text":"Erledigt."}')
        return _ok('{"action":"call","agent":"Schreiber","task":"Schreibe die Styles für .language-card."}')

    second = _second_run(monkeypatch, _complete, first["id"])
    assert second["outcome"] == "succeeded", second.get("error_message")
    record = seen["record"]
    # The record has the old order, the agent call and the final answer.
    assert "Bau eine Hello-World-App mit bunten Karten." in record
    assert "Baue die Sprachkarten." in record and "Karten gebaut. Die Styles fehlen noch." in record
    assert "Fertig: Karten gebaut, Styles offen." in record
    # The new request stays out: run bd3cfb0f wrote it into the briefing as a conflict.
    assert "Mach die Styles fertig." not in record
    assert not seen["tools"]
    # Only the orchestrator gets the briefing, as data in front of the user's message.
    orch = seen["orch"]
    assert "<previous_run" in orch and _BRIEFING in orch
    assert "The agents do not see it" in orch
    assert "what the agents report in this run is newer and replaces it" in orch
    assert orch.index(_BRIEFING) < orch.index("Mach die Styles fertig.")
    assert seen["agent"] and all(_BRIEFING not in prompt for prompt in seen["agent"])
    # The user sees it in the chat; the course and the log keep it.
    briefings = [item for item in second["chat"] if item.get("messageKey") == "monitoring.chat.briefing"]
    assert briefings and briefings[0]["messageParams"]["text"] == _BRIEFING
    assert [turn["kind"] for turn in second["memory"]["turns"]][:2] == ["briefing", "user"]
    done = [row["payload"] for row in list_logs(second["id"]) if row["message"] == "run.briefing.done"]
    assert done == [{"previousRunId": first["id"], "analyzed": True, "chars": len(_BRIEFING), "outcome": "succeeded"}]


def test_without_the_analysis_the_shortened_record_stands_in(monkeypatch, api_env) -> None:
    first = _first_run(monkeypatch)
    prompts: list[str] = []

    def _complete(req, should_abort=None, on_progress=None):
        if _is_analysis(req):
            raise RuntimeApiError("runtime.upstream")
        if not _is_orch(req):
            return _ok("ok")
        prompts.append(_blob(req))
        return _ok('{"action":"finish","text":"Erledigt."}')

    second = _second_run(monkeypatch, _complete, first["id"])
    assert second["outcome"] == "succeeded", second.get("error_message")
    assert "<previous_run" in prompts[0] and "Bau eine Hello-World-App mit bunten Karten." in prompts[0]
    logs = list_logs(second["id"])
    assert [row["payload"]["error"] for row in logs if row["message"] == "run.briefing.failed"] == ["runtime.upstream"]
    assert [row["payload"]["analyzed"] for row in logs if row["message"] == "run.briefing.done"] == [False]


def test_the_choice_is_checked(monkeypatch, api_env) -> None:
    from app.http.errors import AppError
    from app.run.controller import get_controller
    from app.run.previous_run import list_previous

    first = _first_run(monkeypatch)

    def _complete(req, should_abort=None, on_progress=None):
        return _ok('{"action":"finish","text":"Erledigt."}')

    monkeypatch.setattr("app.runtime.completions.complete_live", _complete)
    ctrl = get_controller()
    started = ctrl.start()
    for _ in range(200):
        if ctrl.service_status == "running":
            break
        time.sleep(0.01)
    items = list_previous(ctrl.network_id, ctrl.run_id)
    assert [item["runId"] for item in items] == [first["id"]]
    assert items[0]["request"] == "Bau eine Hello-World-App mit bunten Karten."
    # Not a run of this network, and not the running run itself.
    for bad in ("no-such-run", started["runId"]):
        with pytest.raises(AppError) as error:
            ctrl.send_chat("Weiter.", previous_run_id=bad)
        assert error.value.message_key == "run.previousInvalid"
    ctrl.send_chat("Weiter.")
    ctrl.thread.join(timeout=5)
    assert ctrl.previous_run_id is None


def test_the_record_keeps_the_first_and_the_latest_calls() -> None:
    from app.run.previous_run import RECORD_MAX_CHARS, previous_record

    calls = [
        {"name": "Coder", "task": f"Aufgabe {index} " + "x" * 300, "text": "Antwort " + "y" * 600, "files": []}
        for index in range(1, 60)
    ]
    calls[-1]["files"] = [{"tool": "file_access", "action": "write", "path": "src/cards.scss"}]
    row = {
        "network_name": "Coder_Team",
        "started_at": "2026-11-20T18:19:50+00:00",
        "ended_at": "2026-11-20T19:44:11+00:00",
        "outcome": "failed",
        "error_message": "run.orchestrator.stuck",
        "chat": [{"role": "user", "content": "überprüfe bitte die letzte arbeit"}],
        "memory": {
            "turns": [{"role": "user", "kind": "briefing", "text": "Älterer Auftrag: Karten in Sprachfarben."}],
            "calls": calls,
        },
    }
    text = previous_record(row, [])
    assert len(text) <= RECORD_MAX_CHARS
    assert "outcome failed, error run.orchestrator.stuck" in text
    assert "überprüfe bitte die letzte arbeit" in text
    # A run that continued from another one passes that briefing on.
    assert "Älterer Auftrag: Karten in Sprachfarben." in text
    assert "(none: the run ended without one)" in text
    assert "1. Coder: task: Aufgabe 1 " in text and "59. Coder: task: Aufgabe 59 " in text
    assert "calls left out" in text
    assert "Files changed: src/cards.scss" in text


def test_the_record_of_an_old_run_comes_from_the_log() -> None:
    from app.run.previous_run import previous_record

    row = {"outcome": "succeeded", "chat": [], "memory": None}
    logs = [
        {"message": "run.agent.done", "payload": {"agentName": "Junior", "task": "Baue X", "result": "X steht", "outcome": "done"}},
        {"message": "run.summary", "payload": {"files": ["src/x.ts"]}},
    ]
    text = previous_record(row, logs)
    assert "1. Junior: task: Baue X | done | answer: X steht" in text
    assert "Files changed: src/x.ts" in text
