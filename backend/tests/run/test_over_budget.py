"""Dev Team run, 2026-11-17 (23:27): a green build, then the run failed as unreadable.

After its read budget the orchestrator wrote three more reads as tool-call text.
That was a clear request, not an unreadable answer: the next decision gets a new
budget. The agent prompt now says the result is the reply, not a file.
"""

from __future__ import annotations

from app.db.runs import list_logs
from app.run.limits import MAX_READ_DECISION_CALLS
from app.runtime.models import CompletionResult, ToolCall
from app.tools.models import ExecuteResult
from tests.run.test_harness import _drive, _orch_files_doc

_XML = (
    "<tool_call>\n<function=file_access>\n<parameter=action>\nread\n</parameter>\n"
    "<parameter=path>\nsrc/data/greetings.ts\n</parameter>\n</function>\n</tool_call>"
)


def _is_orch(req) -> bool:
    return "You orchestrate" in (req.messages[0].content or "")


def _blob(req) -> str:
    return "\n".join(message.content or "" for message in req.messages)


def _ok(text: str) -> CompletionResult:
    return CompletionResult(content=text, model="m", finish_reason="stop")


def _payloads(stored: dict, message: str) -> list[dict]:
    return [row["payload"] or {} for row in list_logs(stored["id"]) if row["message"] == message]


def test_reads_written_as_text_over_the_budget_get_a_new_decision(monkeypatch, api_env) -> None:
    executed: list[str] = []

    def _execute(kind, *, config, args, secret=None):
        executed.append(str(args.get("path")))
        return ExecuteResult(ok=True, result={"path": str(args.get("path")), "content": "x"})

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)
    state = {"read": 0, "decisions_with_tools": 0, "note": False}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("Build ok.")
        blob = _blob(req)
        if "characters:" not in blob:
            return _ok('{"action":"call","agent":"Schreiber","task":"bau"}')
        if "The tool steps you wrote as text did not run" in blob:
            state["note"] = True
        if req.tools and state["note"]:
            if "src/data/greetings.ts" in executed:
                return _ok('{"action":"finish","text":"Fertig."}')
            return CompletionResult(
                content=None,
                tool_calls=[ToolCall(id="g", name="file_access", arguments='{"action":"read","path":"src/data/greetings.ts"}')],
                model="m",
                finish_reason="tool_calls",
            )
        if req.tools:
            first = state["read"]
            state["read"] += 5
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id=f"r{first + i}", name="file_access", arguments=f'{{"action":"read","path":"f{first + i}"}}')
                    for i in range(5)
                ],
                model="m",
                finish_reason="tool_calls",
            )
        # Budget used up: the model keeps writing the next read as markup, also after the note.
        return _ok("Ich lese noch greetings.ts.\n\n" + _XML)

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert state["note"] is True
    assert executed[:MAX_READ_DECISION_CALLS] == [f"f{i}" for i in range(MAX_READ_DECISION_CALLS)]
    assert executed[-1] == "src/data/greetings.ts"
    requests = _payloads(stored, "run.orchestrator.toolRequest")
    assert requests == [{"verb": "read", "granted": False, "overBudget": True}]
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert "run.orchestrator.unreadable" not in messages
    assert not any("<tool_call>" in (item["content"] or "") for item in (stored["chat"] or []))


def test_reading_the_same_files_again_and_again_still_stops(monkeypatch, api_env) -> None:
    """The new budget is no loophole: re-reading what was read counts as no progress."""

    def _execute(kind, *, config, args, secret=None):
        return ExecuteResult(ok=True, result={"path": str(args.get("path")), "content": "x"})

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)
    state = {"called": False}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("Build ok.")
        if not state["called"]:
            state["called"] = True
            return _ok('{"action":"call","agent":"Schreiber","task":"bau"}')
        if req.tools:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id=f"r{i}", name="file_access", arguments=f'{{"action":"read","path":"f{i}"}}')
                    for i in range(MAX_READ_DECISION_CALLS)
                ],
                model="m",
                finish_reason="tool_calls",
            )
        return _ok(_XML)

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.orchestrator.stuck"


def test_agent_prompt_says_the_result_is_the_reply_not_a_file(monkeypatch, api_env) -> None:
    from tests.run.test_harness import _linear_file_doc

    seen: list[str] = []

    def _complete(req, should_abort=None, on_progress=None):
        seen.append(req.messages[0].content or "")
        return _ok("Fertig.")

    stored = _drive(monkeypatch, _complete, doc=_linear_file_doc(), user_texts=())
    assert stored["outcome"] == "succeeded"
    assert "Your result is your reply text, not a file" in seen[0]
