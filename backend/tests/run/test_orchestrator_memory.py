"""O1/O2: orchestrator plans stay in the course; a blocked reply is reported, not dropped."""

from __future__ import annotations

import json

from app.run.memory import RunMemory
from app.runtime.models import CompletionRequest, CompletionResult
from tests.run.test_harness import _drive


def _orch_prompt(req: CompletionRequest) -> str | None:
    system = req.messages[0].content or ""
    if "You orchestrate" not in system:
        return None
    return "\n".join(message.content or "" for message in req.messages[1:])


def test_think_is_kept_in_protocol_form() -> None:
    memory = RunMemory()
    memory.add_user("Bau mir eine Seite")
    assert memory.add_think("Erst Schreiber mit dem Gerüst beauftragen.") is False
    messages = memory.orchestrator_messages("sys")
    thinks = [m for m in messages if m.role == "assistant"]
    assert len(thinks) == 1
    assert json.loads(thinks[0].content) == {
        "action": "think",
        "text": "Erst Schreiber mit dem Gerüst beauftragen.",
    }
    # A trailing assistant turn would be continued as a prefill; the prompt must end on user.
    assert messages[-1].role == "user"


def test_thinks_are_capped_and_trimmed() -> None:
    memory = RunMemory()
    for index in range(7):
        memory.add_think(f"plan {index}")
    kept = [turn.text for turn in memory.turns if turn.kind == "think"]
    assert kept == ["plan 3", "plan 4", "plan 5", "plan 6"]
    memory.add_think("x" * 2000)
    longest = max(len(turn.text) for turn in memory.turns if turn.kind == "think")
    assert longest == 600


def test_repeat_is_detected_and_placeholders_ignored() -> None:
    memory = RunMemory()
    assert memory.add_think("…") is False
    assert memory.turns == []
    assert memory.add_think("Datei prüfen") is False
    assert memory.add_think("  Datei   prüfen ") is True


def test_nudge_is_replaced_not_stacked() -> None:
    memory = RunMemory()
    memory.set_nudge("eins")
    memory.set_nudge("zwei")
    assert [turn.text for turn in memory.turns if turn.kind == "nudge"] == ["zwei"]
    memory.clear_nudge()
    assert not any(turn.kind == "nudge" for turn in memory.turns)


def test_next_decision_sees_the_previous_plan(monkeypatch, api_env) -> None:
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        blob = _orch_prompt(req)
        if blob is None:
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        prompts.append(blob)
        if len(prompts) == 1:
            content = '{"action":"think","text":"Zuerst den Schreiber beauftragen."}'
        elif "Result from Schreiber" in blob:
            content = '{"action":"finish","text":"Fertig."}'
        else:
            content = '{"action":"call","agent":"Schreiber","task":"schreib"}'
        return CompletionResult(content=content, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    assert "Zuerst den Schreiber beauftragen." not in prompts[0]
    assert "Zuerst den Schreiber beauftragen." in prompts[1]
    turns = stored["memory"]["turns"]
    assert any(turn["kind"] == "think" for turn in turns)


def test_blocked_reply_is_reported_and_run_recovers(monkeypatch, api_env) -> None:
    """Before: the second reply vanished and the identical prompt looped to thinkLimit."""
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        blob = _orch_prompt(req)
        if blob is None:
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        prompts.append(blob)
        if "not shown: you already replied" in blob:
            content = '{"action":"finish","text":"Alles erledigt."}'
        elif len(prompts) == 1:
            content = '{"action":"reply","text":"Ich lege los."}'
        else:
            content = '{"action":"reply","text":"Fertig!"}'
        return CompletionResult(content=content, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    assert len(prompts) == 3
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Ich lege los." in texts
    assert "Fertig!" not in texts
    assert "Alles erledigt." in texts
    # The blocked text is visible to the model as its own plan.
    assert '"text": "Fertig!"' in prompts[2]
    # The hint is gone once a real action ran.
    assert not any(turn["kind"] == "nudge" for turn in stored["memory"]["turns"])


def test_repeated_plan_gets_a_nudge(monkeypatch, api_env) -> None:
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        blob = _orch_prompt(req)
        if blob is None:
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        prompts.append(blob)
        if "You repeated the same plan" in blob:
            content = '{"action":"finish","text":"Ok."}'
        else:
            content = '{"action":"think","text":"Ich überlege noch."}'
        return CompletionResult(content=content, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    assert len(prompts) == 3
