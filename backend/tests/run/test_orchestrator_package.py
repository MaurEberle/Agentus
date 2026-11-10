"""O9-O20 package: own results, private reasoning, several JSON objects, run budget,
takeover, model pause, bounded persistence, logging, role order."""

from __future__ import annotations

import threading
import time

from app.db.runs import list_logs
from app.run.memory import RunMemory, ToolEvent
from app.run.orchestrate import parse_orchestrator_action
from app.runtime.errors import RuntimeApiError
from app.runtime.models import CompletionRequest, CompletionResult
from tests.run.test_harness import _drive


def _is_orch(req: CompletionRequest) -> bool:
    return "You orchestrate" in (req.messages[0].content or "")


def _logs(stored: dict) -> list[dict]:
    return list_logs(stored["id"])


def _messages(stored: dict) -> list[str]:
    return [row["message"] for row in _logs(stored)]


# O9 -----------------------------------------------------------------------
def test_own_results_stay_visible_and_bounded() -> None:
    memory = RunMemory()
    for index in range(5):
        memory.note_own_tool(ToolEvent(name="web_search", arguments="{}", ok=True, result=f"hit {index} " + "x" * 3000), None)
    blob = memory.prompt_text("sys")
    assert "hit 4" in blob and "hit 2" in blob and "hit 1" not in blob
    assert blob.count("<tool_result") == 3
    assert "characters of this tool result omitted" in blob


# O10 ----------------------------------------------------------------------
def test_reasoning_only_answer_is_not_published(monkeypatch, api_env) -> None:
    orch_n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if not _is_orch(req):
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        orch_n["n"] += 1
        if orch_n["n"] == 1:
            return CompletionResult(
                content="", reasoning="Ich überlege intern, welcher Agent passt.", model=req.model, finish_reason="stop"
            )
        return CompletionResult(content='{"action":"finish","text":"Fertig."}', model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert not any("überlege intern" in text for text in texts)
    assert "run.orchestrator.privateReasoning" in _messages(stored)


def test_visible_prose_is_still_a_reply() -> None:
    assert parse_orchestrator_action("Hallo, ich helfe dir gern.")["action"] == "reply"


# O11 ----------------------------------------------------------------------
def test_executable_object_wins_over_think() -> None:
    raw = '{"action":"think","text":"plan"}\n{"action":"call","agent":"Schreiber","task":"schreib"}'
    parsed = parse_orchestrator_action(raw)
    assert parsed["action"] == "call" and parsed["agent"] == "Schreiber"


def test_reply_wins_over_think_and_first_think_otherwise() -> None:
    assert parse_orchestrator_action('{"action":"think","text":"a"}{"action":"reply","text":"b"}')["text"] == "b"
    assert parse_orchestrator_action('{"action":"think","text":"a"}{"action":"think","text":"b"}')["text"] == "a"


# O19 ----------------------------------------------------------------------
def test_nested_text_stays_json() -> None:
    parsed = parse_orchestrator_action('{"action":"reply","text":{"de":"Hallo"}}')
    assert parsed["text"] == '{"de": "Hallo"}'


# O12 ----------------------------------------------------------------------
def test_run_budget_ends_the_run(monkeypatch, api_env) -> None:
    monkeypatch.setattr("app.run.limits.MAX_RUN_LLM_CALLS", 3)
    calls = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        calls["n"] += 1
        return CompletionResult(content=f'{{"action":"think","text":"Schritt {calls["n"]}"}}', model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.llmBudget"
    assert stored["error_class"] == "budget"
    assert calls["n"] == 3


# O14 ----------------------------------------------------------------------
def test_unreachable_model_pauses_and_resumes(monkeypatch, api_env) -> None:
    from app.run.controller import get_controller

    state = {"down": 2}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if not _is_orch(req):
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        if state["down"] > 0:
            state["down"] -= 1
            raise RuntimeApiError("runtime.unreachable")
        return CompletionResult(content='{"action":"finish","text":"Wieder da."}', model=req.model, finish_reason="stop")

    def _answer_pause() -> None:
        ctrl = get_controller()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if ctrl._wait_ask is not None:
                ctrl.chat_input_queue.put("nochmal")
                return
            time.sleep(0.02)

    helper = threading.Thread(target=_answer_pause, daemon=True)
    helper.start()
    stored = _drive(monkeypatch, _complete)
    helper.join(timeout=5)
    assert stored["outcome"] == "succeeded"
    chat = stored["chat"] or []
    assert any(item.get("messageKey") == "monitoring.chat.llmRetry" for item in chat)
    assert "Wieder da." in [item["content"] for item in chat]
    assert "run.orchestrator.llmPause" in _messages(stored)


# O15 ----------------------------------------------------------------------
def test_persisted_memory_is_bounded() -> None:
    memory = RunMemory()
    for index in range(120):
        memory.note_window("m", context_max=8192, need=index)
        memory.note_own_tool(ToolEvent(name="http", arguments="{}", ok=True, result="y" * 9000), None)
    stored = memory.to_dict()
    assert len(stored["windows"]) == 50
    assert len(stored["ownTools"]) == 50
    assert all(len(item["result"]) <= 2000 for item in stored["ownTools"])
    # The live course is untouched.
    assert len(memory.windows) == 120


# O16 / O17 -----------------------------------------------------------------
def test_call_log_has_token_and_empty_task_is_logged(monkeypatch, api_env) -> None:
    orch_n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if not _is_orch(req):
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        orch_n["n"] += 1
        if orch_n["n"] == 1:
            return CompletionResult(content='{"action":"call","agent":"schreiber"}', model=req.model, finish_reason="stop")
        return CompletionResult(content='{"action":"finish","text":"Fertig."}', model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    action = next(
        row for row in _logs(stored)
        if row["message"] == "run.orchestrator.action" and (row.get("payload") or {}).get("action") == "call"
    )
    assert action["payload"]["requested"] == "schreiber"
    assert action["payload"]["agent"] == "ag"
    assert "run.orchestrator.emptyTask" in _messages(stored)


# O20 ----------------------------------------------------------------------
def test_no_two_user_messages_in_a_row() -> None:
    memory = RunMemory()
    memory.add_user("Start")
    memory.add_note("Hinweis eins")
    record = memory.begin_call("ag", "Schreiber", "t", has_tools=False)
    record.text = "Ergebnis"
    record.finished = True
    messages = memory.orchestrator_messages("sys")
    roles = [m.role for m in messages]
    assert all(not (a == b == "user") for a, b in zip(roles, roles[1:]))
    joined = "\n".join(m.content or "" for m in messages)
    assert "Start" in joined and "Hinweis eins" in joined and "Result from Schreiber" in joined
