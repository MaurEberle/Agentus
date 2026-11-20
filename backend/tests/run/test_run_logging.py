"""Readable run logs (fix/analyse/logging.md, B2 to B8).

Tool and model lines name their caller, agent calls log task and result once,
the orchestrator logs what it decided and how long its tool rounds took, and
every run ends with a summary line.
"""

from __future__ import annotations

import json

from app.db.runs import list_logs
from app.runtime.models import CompletionResult, ToolCall
from app.tools.models import ExecuteResult
from tests.run.conftest import mini_doc
from tests.run.test_harness import _drive, _orch_files_doc


def _rows(stored: dict, message: str) -> list[dict]:
    return [row for row in list_logs(stored["id"]) if row["message"] == message]


def _payload(row: dict) -> dict:
    return row.get("payload") or {}


def _is_orch(req) -> bool:
    return "You orchestrate" in (req.messages[0].content or "")


def _ok(text: str) -> CompletionResult:
    return CompletionResult(content=text, model="m", finish_reason="stop")


def _calls(*items: tuple[str, str]) -> CompletionResult:
    return CompletionResult(
        content=None,
        tool_calls=[ToolCall(id=f"c{i}", name=name, arguments=args) for i, (name, args) in enumerate(items)],
        model="m",
        finish_reason="tool_calls",
    )


def _team_doc() -> dict:
    """Orchestrator with read access, and the agent Schreiber with its own file tool."""
    doc = _orch_files_doc()
    doc["nodes"].append(
        {
            "id": "afiles",
            "type": "tool",
            "position": {"x": 0, "y": 0},
            "data": {"kind": "file_access", "rootPath": "C:/stories"},
        }
    )
    doc["edges"].append(
        {"id": "eat", "source": "afiles", "sourceHandle": "tool", "target": "ag", "targetHandle": "tool"}
    )
    return doc


def _files(monkeypatch) -> None:
    def _execute(kind, *, config, args, secret=None):
        del kind, config, secret
        action = args.get("action")
        if action == "read":
            return ExecuteResult(ok=True, result={"path": args.get("path"), "content": "a\nb\nc\n", "bytes": 6})
        if action == "write":
            return ExecuteResult(ok=True, result={"path": args.get("path"), "bytes": len(args.get("content") or "")})
        return ExecuteResult(ok=True, result={"path": ".", "entries": [{"name": "x", "type": "file"}]})

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)


_RESULT = "Ich habe story.txt geschrieben. " + "y" * 420
_BIG = "x" * 5000


def _team_run(monkeypatch, *, decide_with_tool: bool = False) -> dict:
    _files(monkeypatch)
    orch_calls = {"n": 0}
    agent_calls = {"n": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if _is_orch(req):
            orch_calls["n"] += 1
            if orch_calls["n"] == 1:
                return _calls(("file_access", '{"action":"read","path":"README.md"}'))
            if orch_calls["n"] == 2:
                if decide_with_tool:
                    return _calls(("call_agent", '{"agent":"Schreiber","task":"Schreib die Datei story.txt"}'))
                return _ok('{"action":"call","agent":"Schreiber","task":"Schreib die Datei story.txt"}')
            return _ok('{"action":"finish","text":"Fertig."}')
        agent_calls["n"] += 1
        if agent_calls["n"] == 1:
            args = json.dumps({"action": "write", "path": "story.txt", "content": _BIG})
            return _calls(("file_access", args))
        return _ok(_RESULT)

    stored = _drive(monkeypatch, _complete, doc=_team_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    return stored


def test_tool_lines_name_the_caller_and_what_the_tool_did(monkeypatch, api_env) -> None:
    stored = _team_run(monkeypatch)
    tools = [_payload(row) for row in _rows(stored, "run.tool.call")]
    assert len(tools) == 2
    read, write = tools
    assert read["caller"] == "orch"
    assert read["result"] == {"path": "README.md", "bytes": 6, "lines": 3}
    assert isinstance(read["durationMs"], int)
    assert "changed" not in read
    assert write["caller"] == "ag" and write["callerName"] == "Schreiber"
    assert write["changed"] == "story.txt"
    assert write["result"] == {"path": "story.txt", "bytes": 5000}
    # B5: the file content is clipped to 2 KB in the log; the tool got all of it.
    content = json.loads(write["arguments"])["content"]
    assert content.startswith("x" * 2048) and content.endswith("… [+2952]")


def test_model_lines_are_info_with_caller_and_speed(monkeypatch, api_env) -> None:
    stored = _team_run(monkeypatch)
    done = _rows(stored, "run.llm.done")
    assert done and all(row["level"] == "info" for row in done)
    callers = {_payload(row)["caller"] for row in done}
    assert callers == {"orch", "ag"}
    first = _payload(done[0])
    assert first["model"] and "perSecond" in first and "durationMs" in first
    tool_turn = next(_payload(row) for row in done if _payload(row).get("toolCalls"))
    assert tool_turn["toolCalls"] == ["file_access"]
    starts = _rows(stored, "run.llm.start")
    assert starts and all(row["level"] == "debug" for row in starts)


def test_agent_call_logs_task_and_result_once(monkeypatch, api_env) -> None:
    stored = _team_run(monkeypatch)
    starts = [_payload(row) for row in _rows(stored, "run.agent.start")]
    assert starts == [
        {"agentId": "ag", "agentName": "Schreiber", "task": "Schreib die Datei story.txt", "call": 1}
    ]
    dones = _rows(stored, "run.agent.done")
    assert len(dones) == 1 and dones[0]["level"] == "info"
    done = _payload(dones[0])
    assert done["outcome"] == "done"
    assert done["agentName"] == "Schreiber" and done["call"] == 1
    assert done["tools"] == 1 and done["toolsOk"] == 1 and done["toolsFailed"] == 0
    assert done["files"] == ["story.txt"] and done["filesCount"] == 1
    assert done["result"].startswith("Ich habe story.txt geschrieben.")
    assert done["result"].endswith("… [+" + str(len(_RESULT) - 300) + "]")
    assert done["resultChars"] == len(_RESULT)
    assert isinstance(done["durationMs"], int)


def test_orchestrator_action_names_agent_task_and_way(monkeypatch, api_env) -> None:
    stored = _team_run(monkeypatch)
    actions = [_payload(row) for row in _rows(stored, "run.orchestrator.action")]
    call = next(item for item in actions if item["action"] == "call")
    assert call["agentName"] == "Schreiber"
    assert call["task"] == "Schreib die Datei story.txt"
    assert call["via"] == "json"
    finish = next(item for item in actions if item["action"] == "finish")
    assert finish["text"] == "Fertig."


def test_decision_tool_is_logged_as_the_way(monkeypatch, api_env) -> None:
    stored = _team_run(monkeypatch, decide_with_tool=True)
    actions = [_payload(row) for row in _rows(stored, "run.orchestrator.action")]
    call = next(item for item in actions if item["action"] == "call")
    assert call["via"] == "tool"


def test_orchestrator_step_line_for_a_decision_with_tools(monkeypatch, api_env) -> None:
    stored = _team_run(monkeypatch)
    steps = [_payload(row) for row in _rows(stored, "run.orchestrator.step")]
    assert len(steps) == 1
    step = steps[0]
    assert step["calls"] == 1 and step["failed"] == 0
    assert step["end"] == "call"
    assert step["capped"] is False and step["withdrawn"] == []
    assert isinstance(step["durationMs"], int)


def test_run_ends_with_a_summary(monkeypatch, api_env) -> None:
    stored = _team_run(monkeypatch)
    rows = list_logs(stored["id"])
    summary_rows = [row for row in rows if row["message"] == "run.summary"]
    assert len(summary_rows) == 1
    summary = _payload(summary_rows[0])
    assert summary["outcome"] == "succeeded"
    assert summary["agentCalls"] == 1
    assert summary["agents"][0]["name"] == "Schreiber" and summary["agents"][0]["calls"] == 1
    assert summary["toolCalls"] == 2 and summary["toolsOk"] == 2 and summary["toolsFailed"] == 0
    assert summary["tools"] == {"file_access": 2}
    assert summary["files"] == ["story.txt"] and summary["filesCount"] == 1
    assert summary["llmCalls"] == len(_rows(stored, "run.llm.done"))
    assert summary["limits"] == {}
    assert "error" not in summary
    assert isinstance(summary["durationMs"], int)


def test_linear_agent_logs_start_done_and_clips_model_text(monkeypatch, api_env) -> None:
    answer = "z" * 9000

    def _complete(req, should_abort=None, on_progress=None):
        return _ok(answer)

    stored = _drive(monkeypatch, _complete, doc=mini_doc(startMessage="go"), user_texts=())
    assert stored["outcome"] == "succeeded"
    start = _payload(_rows(stored, "run.agent.start")[0])
    assert start["agentId"] == "ag" and start["task"] == "go"
    done = _payload(_rows(stored, "run.agent.done")[0])
    assert done["outcome"] == "done" and done["tools"] == 0 and done["resultChars"] == 9000
    llm = _payload(_rows(stored, "run.llm.done")[0])
    assert llm["content"] == "z" * 8000 + "… [+1000]"
    summary = _payload(_rows(stored, "run.summary")[0])
    assert summary["agentCalls"] == 1 and summary["llmCalls"] == 1


def test_failed_run_summary_names_the_error(monkeypatch, api_env) -> None:
    def _complete(req, should_abort=None, on_progress=None):
        raise RuntimeError("model exploded")

    stored = _drive(monkeypatch, _complete, doc=mini_doc(startMessage="go"), user_texts=())
    assert stored["outcome"] == "failed"
    summary = _payload(_rows(stored, "run.summary")[0])
    assert summary["outcome"] == "failed"
    assert summary["error"] == "model exploded"
    assert summary["errors"] >= 1
    assert summary["agentCalls"] == 0
