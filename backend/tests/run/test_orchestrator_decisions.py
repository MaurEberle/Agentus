"""Dev Team run, 2026-11-17 (19:52): the orchestrator read one file 43 times while writing "now I call the Junior".

Decision tools next to own tools, repeated calls that do not run, the note for an
announcement without a decision, and the read budget of ten per decision.
"""

from __future__ import annotations

import json

from app.db.runs import list_logs
from app.run.orchestrate import orchestrator_instructions
from app.runtime.models import CompletionResult, ToolCall
from app.tools.models import ExecuteResult
from tests.run.test_harness import _drive, _orch_files_doc


def _payloads(stored: dict, message: str) -> list[dict]:
    return [row["payload"] or {} for row in list_logs(stored["id"]) if row["message"] == message]


def _is_orch(req) -> bool:
    return "You orchestrate" in (req.messages[0].content or "")


def _blob(req) -> str:
    return "\n".join(message.content or "" for message in req.messages)


def _names(req) -> list[str]:
    return [str((item.get("function") or {}).get("name")) for item in (req.tools or [])]


def _ok(text: str) -> CompletionResult:
    return CompletionResult(content=text, model="m", finish_reason="stop")


def _calls(*items: tuple[str, str], content: str | None = None) -> CompletionResult:
    return CompletionResult(
        content=content,
        tool_calls=[ToolCall(id=f"c{i}", name=name, arguments=args) for i, (name, args) in enumerate(items)],
        model="m",
        finish_reason="tool_calls",
    )


def _record_execute(monkeypatch) -> list[dict]:
    executed: list[dict] = []

    def _execute(kind, *, config, args, secret=None):
        del config, secret
        executed.append({"kind": kind, **dict(args or {})})
        return ExecuteResult(ok=True, result={"path": str(args.get("path") or "."), "text": "x"})

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)
    return executed


def test_the_orchestrator_can_decide_with_a_tool_call(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    seen: dict = {}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            seen["agent_task"] = _blob(req)
            return _ok("a.txt ist fertig.")
        seen.setdefault("names", _names(req))
        if "characters:" in _blob(req):
            return _calls(("finish", '{"text":"Fertig, a.txt steht."}'))
        # A read and the decision in one answer: the decision wins, the read does not run.
        return _calls(
            ("file_access", '{"action":"read","path":"plan.md"}'),
            ("call_agent", '{"agent":"Schreiber","task":"Schreib a.txt."}'),
        )

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert {"call_agent", "ask_user", "reply", "finish"} <= set(seen["names"])
    assert "Schreib a.txt." in seen["agent_task"]
    assert executed == []
    decisions = _payloads(stored, "run.orchestrator.decisionTool")
    assert decisions == [{"name": "call_agent", "dropped": 1}, {"name": "finish", "dropped": 0}]
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Fertig, a.txt steht." in texts


def test_the_same_call_twice_does_not_run_again(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    state = {"rounds": 0}
    last: dict = {}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("Plan steht.")
        blob = _blob(req)
        if "characters:" not in blob:
            return _ok('{"action":"call","agent":"Schreiber","task":"plane"}')
        if not req.tools:
            last["tools"] = req.tools
            return _ok('{"action":"finish","text":"Fertig."}')
        state["rounds"] += 1
        return _calls(("file_access", '{"path":"ARCHITECTURE.md","action":"read","offset":1050}'))

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert len(executed) == 1
    assert state["rounds"] == 3
    assert len(_payloads(stored, "run.orchestrator.toolRepeated")) == 2
    assert _payloads(stored, "run.orchestrator.toolWithdrawn") == [{"name": "file_access", "error": "tool.repeated"}]
    assert last["tools"] is None


def test_an_announcement_without_a_decision_is_answered(monkeypatch, api_env) -> None:
    _record_execute(monkeypatch)
    state = {"read": 0}
    noted: dict = {}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("Plan steht.")
        blob = _blob(req)
        if "characters:" not in blob:
            return _ok('{"action":"call","agent":"Schreiber","task":"plane"}')
        if "did not decide anything" in blob:
            noted["v"] = True
            return _ok('{"action":"finish","text":"Fertig."}')
        state["read"] += 1
        return _calls(
            ("file_access", f'{{"action":"read","path":"p{state["read"]}.md"}}'),
            content="Jetzt rufe ich den Junior.",
        )

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert noted.get("v") is True
    assert state["read"] == 1


def test_reading_only_allows_ten_calls_per_decision(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    state = {"read": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("Teil fertig.")
        blob = _blob(req)
        if "characters:" not in blob:
            return _ok('{"action":"call","agent":"Schreiber","task":"teil 1"}')
        if req.tools:
            first = state["read"]
            state["read"] += 4
            return _calls(*[("file_access", f'{{"action":"read","path":"f{first + i}.txt"}}') for i in range(4)])
        return _ok('{"action":"finish","text":"Fertig."}')

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert len(executed) == 10
    assert _payloads(stored, "run.orchestrator.toolCap") == [{"calls": 10, "max": 10}]


def test_decision_tools_are_mentioned_only_with_tools() -> None:
    plain = orchestrator_instructions("leite", [("ag", "Schreiber", "schreibe")])
    assert "call_agent" not in plain
    tooled = orchestrator_instructions(
        "leite", [("ag", "Schreiber", "schreibe")], ["file_access"], write_open=False, tool_cap=10
    )
    assert "call call_agent, ask_user, reply or finish" in tooled
    assert "Writing that you will call an agent does not call it." in tooled
    assert "up to 10 tools per decision" in tooled


def test_decision_tool_arguments_become_the_decision() -> None:
    from app.run import orch_tools

    name, raw = orch_tools.decision_from_calls(
        [
            ToolCall(id="1", name="file_access", arguments='{"action":"list","path":"."}'),
            ToolCall(id="2", name="call_agent", arguments='{"agent":"Junior","task":"Setup","source":"Architekt","retry":true}'),
        ]
    )
    assert name == "call_agent"
    assert json.loads(raw) == {
        "action": "call",
        "agent": "Junior",
        "task": "Setup",
        "source": "Architekt",
        "retry": True,
    }
    assert orch_tools.decision_from_calls([ToolCall(id="1", name="file_access", arguments="{}")]) is None
    assert orch_tools.call_key("f", '{"b":1,"a":2}') == orch_tools.call_key("f", '{"a": 2, "b": 1}')
