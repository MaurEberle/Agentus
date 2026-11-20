"""Dev Team run, 2026-11-16: the orchestrator looped instead of taking the task over.

Checking tools from the start, write access after a failure, tool steps written
as JSON, the progress guard, takeover after failed calls, and node limits.
"""

from __future__ import annotations

from app.db.runs import list_logs
from app.runtime.models import CompletionRequest, CompletionResult, ToolCall
from app.tools.models import ExecuteResult
from tests.run.test_harness import _can_write, _drive, _linear_file_doc, _orch_files_doc


def _messages(stored: dict) -> list[str]:
    return [row["message"] for row in list_logs(stored["id"])]


def _payloads(stored: dict, message: str) -> list[dict]:
    return [row["payload"] or {} for row in list_logs(stored["id"]) if row["message"] == message]


def _is_orch(req: CompletionRequest) -> bool:
    return "You orchestrate" in (req.messages[0].content or "")


def _blob(req: CompletionRequest) -> str:
    return "\n".join(message.content or "" for message in req.messages)


def _ok(text: str) -> CompletionResult:
    return CompletionResult(content=text, model="m", finish_reason="stop")


def _record_execute(monkeypatch) -> list[dict]:
    executed: list[dict] = []

    def _execute(kind, *, config, args, secret=None):
        del config, secret
        executed.append({"kind": kind, **dict(args or {})})
        return ExecuteResult(ok=True, result={"path": args.get("path") or ".", "entries": [], "bytes": 1})

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)
    return executed


def test_orchestrator_checks_files_but_may_not_write_before_a_failure(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    rounds = {"n": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("erledigt")
        rounds["n"] += 1
        if rounds["n"] == 1:
            assert req.tools and not _can_write(req)
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id="r", name="file_access", arguments='{"action":"list","path":"."}'),
                    ToolCall(id="w", name="file_access", arguments='{"action":"write","path":"a.txt","content":"x"}'),
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        if rounds["n"] == 2:
            assert "tool.writeLocked" in _blob(req)
            return _ok('{"action":"finish","text":"Fertig."}')
        return _ok('{"action":"finish","text":"Fertig."}')

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded"
    assert [item["action"] for item in executed] == ["list"]
    assert _payloads(stored, "run.orchestrator.toolLocked") == [{"name": "file_access", "error": "tool.writeLocked"}]


def test_write_written_as_json_after_a_failure_opens_write_access(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    state = {"agent": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            state["agent"] += 1
            # First call fails (empty result), the second one finishes part of the work.
            return _ok("" if state["agent"] == 1 else "Teil erledigt, a.txt fehlt noch.")
        blob = _blob(req)
        if any(message.role == "tool" for message in req.messages):
            return _ok('{"action":"finish","text":"Selbst erledigt."}')
        if _can_write(req) and "you may change files yourself now" in blob:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id="w", name="file_access", arguments='{"action":"write","path":"a.txt","content":"x"}')
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        if state["agent"] < 2:
            return _ok('{"action":"call","agent":"Schreiber","task":"schreib a.txt"}')
        # The Dev Team model wrote the file step into the decision instead of a tool call.
        assert not _can_write(req)
        return _ok('{"action":"write","path":"a.txt","content":"x"}')

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert [item["action"] for item in executed] == ["write"]
    assert _payloads(stored, "run.orchestrator.toolRequest")[0] == {"verb": "write", "granted": True}
    assert "run.orchestrator.selfTakeover" in _messages(stored)


def test_write_written_as_json_without_a_failure_stays_with_the_agents(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    seen = {"locked_note": False}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("a.txt ist geschrieben.")
        blob = _blob(req)
        if "characters:" in blob:
            return _ok('{"action":"finish","text":"Fertig."}')
        if "are the agents' work while no agent call has failed" in blob:
            seen["locked_note"] = True
            assert not _can_write(req)
            return _ok('{"action":"call","agent":"Schreiber","task":"schreib a.txt"}')
        return _ok('Ich schreibe selbst. {"action":"write","path":"a.txt","content":"x"}')

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert executed == []
    assert seen["locked_note"] is True
    assert _payloads(stored, "run.orchestrator.toolRequest")[0] == {"verb": "write", "granted": False}
    texts = "\n".join(item["content"] for item in (stored["chat"] or []))
    assert '"action":"write"' not in texts.replace(" ", "")


def test_reply_with_a_pasted_file_change_is_not_shown(monkeypatch, api_env) -> None:
    _record_execute(monkeypatch)
    rounds = {"n": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("ok")
        rounds["n"] += 1
        if rounds["n"] == 1:
            return _ok(
                '{"action":"reply","text":"Ich fixe das. {\\"action\\": \\"write\\", \\"path\\": \\"a.txt\\", '
                '\\"content\\": \\"x\\"}"}'
            )
        return _ok('{"action":"finish","text":"Fertig."}')

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    texts = "\n".join(item["content"] for item in (stored["chat"] or []))
    assert "Ich fixe das" not in texts
    assert "run.orchestrator.toolRequest" in _messages(stored)


def test_unreadable_decisions_after_a_reply_end_the_run(monkeypatch, api_env) -> None:
    rounds = {"n": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("ok")
        rounds["n"] += 1
        if rounds["n"] == 1:
            return _ok('{"action":"reply","text":"Ich bin dran."}')
        return _ok('{"foo": 1}')

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.orchestrator.unreadable"
    # Reply, then two give-ups of three attempts each (first try and two repairs).
    assert rounds["n"] == 1 + 2 * 3


def test_decisions_without_progress_stop_the_run(monkeypatch, api_env) -> None:
    rounds = {"n": 0}
    nudged = {"v": False}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("ok")
        rounds["n"] += 1
        if "decisions in a row without progress" in _blob(req):
            nudged["v"] = True
        if rounds["n"] % 2:
            return _ok(f'{{"action":"reply","text":"Zwischenstand {rounds["n"]}: ich arbeite an Teil {rounds["n"]}."}}')
        return _ok(f'{{"action":"think","text":"Plan {rounds["n"]}: {"x" * rounds["n"]} {rounds["n"] * 7}"}}')

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.orchestrator.stuck"
    assert rounds["n"] == 8
    assert nudged["v"] is True


def test_similar_thoughts_count_as_a_repeated_plan(monkeypatch, api_env) -> None:
    from app.run.memory import RunMemory

    memory = RunMemory()
    assert memory.add_think("Ich fixe alle 6 Dateien selbst: routes, main, App, Header.") is False
    assert memory.add_think("Ich fixe jetzt alle 6 Dateien selbst: routes, main, App und Header.") is True
    assert memory.add_think("Ich rufe den Reviewer für die Abnahme.") is False


def test_two_failed_calls_of_one_agent_open_a_takeover(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    calls = {"agent": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            calls["agent"] += 1
            return _ok("")  # empty result twice: two failed calls in a row
        blob = _blob(req)
        if any(message.role == "tool" for message in req.messages):
            return _ok('{"action":"finish","text":"Selbst erledigt."}')
        if "Takeover is active" in (req.messages[0].content or ""):
            assert _can_write(req)
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id="w", name="file_access", arguments='{"action":"write","path":"a.txt","content":"x"}')
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        del blob
        return _ok('{"action":"call","agent":"Schreiber","task":"schreib a.txt"}')

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    assert calls["agent"] == 2
    start = _payloads(stored, "run.orchestrator.takeoverFailures")
    assert len(start) == 1 and start[0]["failed"] == 2 and start[0]["agent"] == "Schreiber"
    assert [item["action"] for item in executed] == ["write"]
    assert stored["memory"]["takeover"] is None


def test_agent_tool_limit_comes_from_the_node(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    doc = _linear_file_doc()
    next(node for node in doc["nodes"] if node["id"] == "ag")["data"]["maxToolCalls"] = 3

    def _complete(req, should_abort=None, on_progress=None):
        if req.tools:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id=f"r{i}", name="file_access", arguments='{"action":"list","path":"."}')
                    for i in range(2)
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return _ok("Teilergebnis.")

    stored = _drive(monkeypatch, _complete, doc=doc, user_texts=())
    assert stored["outcome"] == "succeeded"
    assert len(executed) == 3
    assert _payloads(stored, "run.agent.toolCap") == [{"calls": 3, "max": 3}]


def test_orchestrator_limits_come_from_the_node(monkeypatch, api_env) -> None:
    executed = _record_execute(monkeypatch)
    doc = _orch_files_doc()
    orch = next(node for node in doc["nodes"] if node["id"] == "orch")
    orch["data"]["maxToolCalls"] = 4
    orch["data"]["maxLlmCalls"] = 10
    rounds = {"n": 0}

    def _complete(req, should_abort=None, on_progress=None):
        if not _is_orch(req):
            return _ok("Teil erledigt.")
        rounds["n"] += 1
        if rounds["n"] == 2 and req.tools:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id=f"r{i}", name="file_access", arguments=f'{{"action":"list","path":"d{i}"}}')
                    for i in range(6)
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return _ok(f'{{"action":"call","agent":"Schreiber","task":"Teil {rounds["n"]}"}}')

    stored = _drive(monkeypatch, _complete, doc=doc)
    assert len(executed) == 4
    assert _payloads(stored, "run.orchestrator.toolCap") == [{"calls": 4, "max": 4}]
    # Orchestrator and agent take turns until the node's budget of ten model calls is used.
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.llmBudget"


def test_node_limits_are_clamped() -> None:
    from app.run.graph_models import AgentNetworkDocument
    from app.run.compile import compile_document

    doc = _orch_files_doc()
    orch = next(node for node in doc["nodes"] if node["id"] == "orch")
    orch["data"].update({"maxToolCalls": 0, "maxLlmCalls": "99999", "agentMissLimit": None, "maxReadCalls": "5000"})
    agent = next(node for node in doc["nodes"] if node["id"] == "ag")
    agent["data"]["maxToolCalls"] = "abc"
    compiled = compile_document(AgentNetworkDocument.model_validate(doc), network_id="n", network_name="n")
    assert compiled.orchestrator.max_tool_calls == 1
    assert compiled.orchestrator.max_llm_calls == 10000
    assert compiled.orchestrator.max_read_calls == 1000
    assert compiled.orchestrator.agent_miss_limit == 2
    assert compiled.agents["ag"].max_tool_calls is None


def test_the_model_sees_the_hint_in_the_tool_result(monkeypatch, api_env, tmp_path) -> None:
    import json

    doc = _linear_file_doc()
    next(node for node in doc["nodes"] if node["id"] == "files")["data"]["rootPath"] = str(tmp_path)
    seen: list[dict] = []

    def _complete(req, should_abort=None, on_progress=None):
        tool_messages = [m for m in req.messages if m.role == "tool"]
        if tool_messages:
            seen.append(json.loads(tool_messages[-1].content or "{}"))
            return CompletionResult(content="Datei fehlt.", model=req.model, finish_reason="stop")
        return CompletionResult(
            content=None,
            tool_calls=[ToolCall(id="r", name="file_access", arguments='{"path":"notes.txt"}')],
            model=req.model,
            finish_reason="tool_calls",
        )

    stored = _drive(monkeypatch, _complete, doc=doc, user_texts=())
    assert stored["outcome"] == "succeeded"
    assert seen[0]["errorKey"] == "tools.fileAccess.invalidAction"
    assert "Every call needs an action" in seen[0]["hint"]
