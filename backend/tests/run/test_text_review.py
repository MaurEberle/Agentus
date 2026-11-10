"""Text-only review (variant C), takeover of tools, unavailable takeover, merge adaptations."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

from app.db.runs import list_logs
from app.run.orchestrate import parse_orchestrator_action
from app.runtime.models import CompletionRequest, CompletionResult, ToolCall
from app.tools.models import ExecuteResult
from tests.run.test_harness import _drive, _takeover_doc, _tool_agent_doc

_CALL = '{"action":"call","agent":"Schreiber","task":"schreib die datei"}'
_RETRY = '{"action":"call","agent":"Schreiber","task":"schreib die datei wirklich mit dem tool","retry":true}'
_FINISH = '{"action":"finish","text":"Fertig."}'


def _is_orch(req: CompletionRequest) -> bool:
    return "You orchestrate" in (req.messages[0].content or "")


def _messages(stored: dict) -> list[str]:
    return [row["message"] for row in list_logs(stored["id"])]


def _ok_tools(monkeypatch, counter: dict | None = None) -> None:
    def _execute(kind, *, config, args, secret=None):
        if counter is not None:
            counter["n"] = counter.get("n", 0) + 1
        return ExecuteResult(ok=True, result={"path": args.get("path") or ".", "entries": []})

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)


# ---------------------------------------------------------------- protocol
def test_retry_flag_is_parsed_only_when_set() -> None:
    assert parse_orchestrator_action(_RETRY)["retry"] == "1"
    assert "retry" not in parse_orchestrator_action(_CALL)
    assert "retry" not in parse_orchestrator_action('{"action":"call","agent":"A","task":"t","retry":false}')


# ---------------------------------------------------------------- text-only flag
def test_text_only_answer_is_finished_and_flagged(monkeypatch, api_env) -> None:
    _ok_tools(monkeypatch)
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if not _is_orch(req):
            return CompletionResult(content="Ich habe gespeichert.", model=req.model, finish_reason="stop")
        prompts.append("\n".join(m.content or "" for m in req.messages))
        return CompletionResult(content=_CALL if len(prompts) == 1 else _FINISH, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert "note: text only" in prompts[1]
    assert stored["memory"]["calls"][0]["textOnly"] is True
    assert stored["memory"]["calls"][0]["error"] == ""
    assert "run.agent.textOnly" in _messages(stored)


# ---------------------------------------------------------------- retries -> takeover
def test_two_failed_retries_open_a_tools_takeover(monkeypatch, api_env) -> None:
    counter: dict = {}
    _ok_tools(monkeypatch, counter)
    agent_calls = {"n": 0}
    orch_tools_seen: list[bool] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if not _is_orch(req):
            # Count tasks, not model calls: a short text answer gets one "answered?" nudge.
            agent_calls["n"] += 1 if len(req.messages) <= 2 else 0
            return CompletionResult(content="Erledigt, versprochen.", model=req.model, finish_reason="stop")
        blob = "\n".join(m.content or "" for m in req.messages)
        if "Takeover for Schreiber" in blob:
            orch_tools_seen.append(bool(req.tools))
            if not any(m.role == "tool" for m in req.messages):
                return CompletionResult(
                    content=None,
                    tool_calls=[ToolCall(id="t1", name="file_access", arguments='{"action":"write","path":"a.txt","content":"x"}')],
                    model=req.model,
                    finish_reason="tool_calls",
                )
        if agent_calls["n"] == 0:
            return CompletionResult(content=_CALL, model=req.model, finish_reason="stop")
        if agent_calls["n"] < 3:
            return CompletionResult(content=_RETRY, model=req.model, finish_reason="stop")
        return CompletionResult(content=_FINISH, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_takeover_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert agent_calls["n"] == 3
    assert orch_tools_seen and orch_tools_seen[0] is True
    assert counter["n"] == 1
    logs = list_logs(stored["id"])
    retries = [row for row in logs if row["message"] == "run.orchestrator.textRetry"]
    assert [row["payload"]["fails"] for row in retries] == [1, 2]
    start = next(row for row in logs if row["message"] == "run.orchestrator.takeoverStart")
    assert start["payload"]["kind"] == "tools"
    # A successful own tool call ended the takeover.
    assert stored["memory"]["takeover"] is None


def test_new_tasks_without_retry_never_count(monkeypatch, api_env) -> None:
    """The planning agent case: text answers to new tasks are no failures."""
    _ok_tools(monkeypatch)
    agent_calls = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if not _is_orch(req):
            agent_calls["n"] += 1
            return CompletionResult(content=f"Plan Teil {agent_calls['n']}.", model=req.model, finish_reason="stop")
        content = _CALL if agent_calls["n"] < 4 else _FINISH
        return CompletionResult(content=content, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_takeover_doc())
    assert stored["outcome"] == "succeeded"
    assert agent_calls["n"] == 4
    messages = _messages(stored)
    assert "run.orchestrator.textRetry" not in messages
    assert "run.orchestrator.takeoverStart" not in messages


def test_retry_that_uses_a_tool_resets_the_count(monkeypatch, api_env) -> None:
    _ok_tools(monkeypatch)
    agent_calls = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if not _is_orch(req):
            if agent_calls["n"] == 1 and not any(m.role == "tool" for m in req.messages):
                return CompletionResult(
                    content=None,
                    tool_calls=[ToolCall(id="w", name="file_access", arguments='{"action":"write","path":"a.txt","content":"x"}')],
                    model=req.model,
                    finish_reason="tool_calls",
                )
            agent_calls["n"] += 1
            return CompletionResult(content="Datei geschrieben.", model=req.model, finish_reason="stop")
        content = _CALL if agent_calls["n"] == 0 else (_RETRY if agent_calls["n"] == 1 else _FINISH)
        return CompletionResult(content=content, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_takeover_doc())
    assert stored["outcome"] == "succeeded"
    assert stored["memory"]["textRetryFails"].get("ag", 0) == 0
    assert "run.orchestrator.takeoverStart" not in _messages(stored)


# ---------------------------------------------------------------- takeover not possible
def _always_retry(agent_text: str = "Nur Text."):
    state = {"agent": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if not _is_orch(req):
            state["agent"] += 1 if len(req.messages) <= 2 else 0
            return CompletionResult(content=agent_text, model=req.model, finish_reason="stop")
        content = _CALL if state["agent"] == 0 else _RETRY
        return CompletionResult(content=content, model=req.model, finish_reason="stop")

    return _complete, state


def test_unavailable_takeover_is_an_anomaly_then_fails_after_three(monkeypatch, api_env) -> None:
    _ok_tools(monkeypatch)
    complete, state = _always_retry()
    stored = _drive(monkeypatch, complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.orchestrator.takeoverNoTool"
    logs = list_logs(stored["id"])
    counts = [row["payload"]["count"] for row in logs if row["message"] == "run.orchestrator.takeoverUnavailable"]
    assert counts == [1, 2, 3, 4]
    # 1 first call + 2 failed retries per unavailable takeover, four times.
    assert state["agent"] == 9


def test_unavailable_takeover_lets_the_orchestrator_decide(monkeypatch, api_env) -> None:
    _ok_tools(monkeypatch)
    state = {"agent": 0}
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if not _is_orch(req):
            state["agent"] += 1
            return CompletionResult(content="Nur Text.", model=req.model, finish_reason="stop")
        blob = "\n".join(m.content or "" for m in req.messages)
        prompts.append(blob)
        if "Takeover is not possible" in blob:
            return CompletionResult(content='{"action":"finish","text":"Datei fehlt noch."}', model=req.model, finish_reason="stop")
        content = _CALL if state["agent"] == 0 else _RETRY
        return CompletionResult(content=content, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert "run.orchestrator.takeoverUnavailable" in _messages(stored)


# ---------------------------------------------------------------- compact summary is accounted
def test_compact_summary_call_is_counted_and_recorded(monkeypatch) -> None:
    from app.run import agent_turn

    charged: list[str] = []
    recorded: list[dict] = []
    requests: list[CompletionRequest] = []
    monkeypatch.setattr("app.run.turn_runtime._charge_llm", lambda ctrl, node_id: charged.append(node_id))
    monkeypatch.setattr(agent_turn, "insert_call", lambda **kw: recorded.append(kw))
    monkeypatch.setattr(agent_turn, "emit_log", lambda *a, **k: None)

    def _complete(req, should_abort=None, on_progress=None):
        requests.append(req)
        return CompletionResult(content="state", model=req.model, finish_reason="stop")

    monkeypatch.setattr("app.runtime.completions.complete_live", _complete)
    ctrl = SimpleNamespace(stop_event=threading.Event(), run_id="r1")
    compiled = SimpleNamespace(by_id={})
    llm = SimpleNamespace(provider="ollama", model="m", base_url=None, credential_id=None, node_id="llm1")
    from app.runtime.models import ChatMessage

    out = agent_turn._compact_state(ctrl, compiled, "ag", llm, [ChatMessage(role="user", content="x")])
    assert out == "state"
    assert charged == ["ag"]
    assert recorded and recorded[0]["ok"] is True and recorded[0]["node_id"] == "ag"
    assert requests[0].max_duration_sec and requests[0].max_duration_sec > 0


# ---------------------------------------------------------------- excel safety
def test_excel_text_file_is_backed_up_before_replacing(tmp_path: Path) -> None:
    from app.mcp.excel_files import ensure_workbook, prepare_excel_write

    text = tmp_path / "liste.xlsx"
    text.write_text("Ticker,Name\n", encoding="utf-8")
    assert ensure_workbook(text)
    assert text.read_bytes()[:2] == b"PK"
    assert (tmp_path / "liste.xlsx.bak").read_text(encoding="utf-8") == "Ticker,Name\n"
    # Relative paths are never written (they would land in the app folder).
    assert prepare_excel_write("excel_write_to_sheet", {"fileAbsolutePath": "relativ.xlsx"}) is False
    assert not Path("relativ.xlsx").exists()


def test_excel_prepare_never_raises(tmp_path: Path, monkeypatch) -> None:
    from app.mcp import excel_files

    def _boom(path):
        raise OSError("locked")

    monkeypatch.setattr(excel_files, "ensure_workbook", _boom)
    assert excel_files.prepare_excel_write("excel_write_to_sheet", {"fileAbsolutePath": str(tmp_path / "x.xlsx")}) is False
