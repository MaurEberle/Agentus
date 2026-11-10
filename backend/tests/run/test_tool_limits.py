"""O4: per-step tool caps (orchestrator 10, agent 50) and per-node maxCalls per run."""

from __future__ import annotations


from app.db.runs import list_logs
from app.runtime.models import CompletionRequest, CompletionResult, ToolCall
from app.tools.models import ExecuteResult
from tests.run.test_harness import _drive, _linear_file_doc, _orch_files_doc



def _orch_tools_from_start(monkeypatch) -> None:
    """These tests exercise the tool loop itself; normally tools open only after an agent fails."""
    from app.run import orchestrator_loop
    from app.run.memory import RunMemory

    class _Open(RunMemory):
        def __init__(self) -> None:
            super().__init__()
            self.allow_own_tools = True

    monkeypatch.setattr(orchestrator_loop, "RunMemory", _Open)

def _ok_execute(counter: dict):
    def _execute(kind, *, config, args, secret=None):
        del kind, config, secret
        counter["n"] += 1
        return ExecuteResult(ok=True, result={"path": args.get("path") or ".", "entries": []})

    return _execute


def _reads(prefix: str, count: int) -> list[ToolCall]:
    return [
        ToolCall(id=f"{prefix}{i}", name="file_access", arguments='{"action":"list","path":"."}')
        for i in range(count)
    ]


def _tool_answers_complete(req: CompletionRequest) -> bool:
    asked = [call.id for m in req.messages if m.role == "assistant" for call in (m.tool_calls or [])]
    answered = [m.tool_call_id for m in req.messages if m.role == "tool"]
    return sorted(asked) == sorted(answered)


def _messages(stored: dict) -> list[str]:
    return [row["message"] for row in list_logs(stored["id"])]


def test_orchestrator_tool_calls_are_capped_per_decision(monkeypatch, api_env) -> None:
    _orch_tools_from_start(monkeypatch)
    executed = {"n": 0}
    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _ok_execute(executed))
    complete_answers: list[bool] = []
    rounds = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" not in system:
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        complete_answers.append(_tool_answers_complete(req))
        if req.tools:
            rounds["n"] += 1
            # Three calls per round: the cap of 10 cuts the fourth round after one call.
            return CompletionResult(
                content=None, tool_calls=_reads(f"r{rounds['n']}_", 3), model=req.model, finish_reason="tool_calls"
            )
        return CompletionResult(content='{"action":"finish","text":"Fertig."}', model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 10
    assert rounds["n"] == 4
    # Every tool_call_id got a tool message, including the two skipped ones (O5 shape).
    assert all(complete_answers)
    assert "run.orchestrator.toolCap" in _messages(stored)


def test_agent_tool_calls_are_capped_per_task(monkeypatch, api_env) -> None:
    executed = {"n": 0}
    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _ok_execute(executed))
    seen_cap_note = {"v": False}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if req.tools:
            return CompletionResult(content=None, tool_calls=_reads("a", 4), model=req.model, finish_reason="tool_calls")
        blob = "\n".join(m.content or "" for m in req.messages)
        seen_cap_note["v"] = "which is the limit" in blob
        return CompletionResult(content="Teilergebnis, Rest offen.", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_linear_file_doc(), user_texts=())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 50
    assert seen_cap_note["v"] is True
    assert "run.agent.toolCap" in _messages(stored)


def test_node_max_calls_limits_one_tool_per_run(monkeypatch, api_env) -> None:
    executed = {"n": 0}
    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _ok_execute(executed))
    doc = _linear_file_doc()
    next(node for node in doc["nodes"] if node["id"] == "files")["data"]["maxCalls"] = 2
    offered_after: list[bool] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        tool_msgs = [m for m in req.messages if m.role == "tool"]
        if any("tool.limitReached" in (m.content or "") for m in tool_msgs):
            offered_after.append(bool(req.tools))
            return CompletionResult(content="Mit zwei Aufrufen erledigt.", model=req.model, finish_reason="stop")
        # Ask for three calls at once: two run, the third is refused by maxCalls.
        return CompletionResult(content=None, tool_calls=_reads("n", 3), model=req.model, finish_reason="tool_calls")

    stored = _drive(monkeypatch, _complete, doc=doc, user_texts=())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 2
    # The exhausted tool is no longer offered.
    assert offered_after == [False]
    messages = _messages(stored)
    assert messages.count("run.tool.limitReached") == 1
    limit_logs = [row for row in list_logs(stored["id"]) if row["message"] == "run.tool.limitReached"]
    assert limit_logs[0]["node_id"] == "files"
    assert (limit_logs[0].get("payload") or {}).get("limit") == 2


def test_refusals_do_not_count_as_tool_failures(monkeypatch, api_env) -> None:
    """Twelve refused calls would trip MAX_FAILED_TOOL_CALLS (10) if they counted."""
    executed = {"n": 0}
    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _ok_execute(executed))
    doc = _linear_file_doc()
    next(node for node in doc["nodes"] if node["id"] == "files")["data"]["maxCalls"] = 1
    turns = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        turns["n"] += 1
        if turns["n"] == 1:
            return CompletionResult(content=None, tool_calls=_reads("x", 13), model=req.model, finish_reason="tool_calls")
        return CompletionResult(content="Fertig.", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=doc, user_texts=())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 1
    assert "run.agent.toolFailures" not in _messages(stored)


def test_unlimited_by_default(monkeypatch, api_env) -> None:
    executed = {"n": 0}
    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _ok_execute(executed))
    turns = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        turns["n"] += 1
        if turns["n"] <= 5:
            return CompletionResult(content=None, tool_calls=_reads(f"u{turns['n']}_", 4), model=req.model, finish_reason="tool_calls")
        return CompletionResult(content="Fertig.", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_linear_file_doc(), user_texts=())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 20
    assert "run.tool.limitReached" not in _messages(stored)


def test_max_calls_validation() -> None:
    from app.run.graph_models import AgentNetworkDocument
    from app.run.validate import validate_document

    def keys(value) -> list[str]:
        doc = _linear_file_doc()
        data = next(node for node in doc["nodes"] if node["id"] == "files")["data"]
        if value is not None:
            data["maxCalls"] = value
        parsed = AgentNetworkDocument.model_validate(doc)
        return [err.message_key for err in validate_document(parsed, data_dir="C:/agentus-data")]

    assert "graph.tool.maxCalls" not in keys(None)
    assert "graph.tool.maxCalls" not in keys(5)
    for bad in (0, -1, "3", True, 2.5):
        assert "graph.tool.maxCalls" in keys(bad), bad
