"""O5: every tool_call_id gets a tool message before the next non-tool message."""

from __future__ import annotations

from app.db.runs import list_logs
from app.run.turn_runtime import _close_open_tool_calls
from app.runtime.errors import RuntimeApiError
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import CompletionRequest, CompletionResult, ToolCall
from app.tools.models import ExecuteResult
from tests.run.test_harness import _drive, _orch_files_doc



def _orch_tools_from_start(monkeypatch) -> None:
    """These tests exercise the tool loop itself; normally tools open only after an agent fails."""
    from app.run import orchestrator_loop
    from app.run.memory import RunMemory

    class _Open(RunMemory):
        def __init__(self) -> None:
            super().__init__()
            self.allow_own_tools = True

    monkeypatch.setattr(orchestrator_loop, "RunMemory", _Open)

def _strict_openai_check(messages: list[LlmMessage]) -> None:
    """Reject like OpenAI: an assistant tool call needs its tool answer before anything else."""
    index = 0
    while index < len(messages):
        message = messages[index]
        index += 1
        ids = {call.id for call in (message.tool_calls or [])} if message.role == "assistant" else set()
        if not ids:
            continue
        while index < len(messages) and messages[index].role == "tool":
            ids.discard(messages[index].tool_call_id)
            index += 1
        if ids:
            raise RuntimeApiError("runtime.badRequest", status=400, detail=f"missing tool answers: {sorted(ids)}")


def _writes(count: int) -> list[ToolCall]:
    return [
        ToolCall(id=f"w{i}", name="file_access", arguments=f'{{"action":"write","path":"f{i}.txt","content":"x"}}')
        for i in range(count)
    ]


def test_think_round_answers_every_call_and_continues(monkeypatch, api_env) -> None:
    _orch_tools_from_start(monkeypatch)
    executed = {"n": 0}

    def _execute(kind, *, config, args, secret=None):
        del kind, config, args, secret
        executed["n"] += 1
        return ExecuteResult(ok=False, result="denied")

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)
    after_round: list[list[LlmMessage]] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        _strict_openai_check(req.messages)
        system = req.messages[0].content or ""
        if "You orchestrate" not in system:
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        if any("Five tool calls failed in a row" in (m.content or "") for m in req.messages):
            after_round.append(list(req.messages))
            return CompletionResult(content='{"action":"finish","text":"Fertig."}', model=req.model, finish_reason="stop")
        # Seven calls in one answer: five fail, then the think round starts.
        return CompletionResult(content=None, tool_calls=_writes(7), model=req.model, finish_reason="tool_calls")

    stored = _drive(monkeypatch, _complete, doc=_orch_files_doc())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 5
    messages = after_round[0]
    tools = [m for m in messages if m.role == "tool"]
    assert [m.tool_call_id for m in tools] == [f"w{i}" for i in range(7)]
    assert all("tool.skipped" in (m.content or "") for m in tools[5:])
    # The think note comes after the last tool answer, not between them.
    note_at = next(i for i, m in enumerate(messages) if "Five tool calls failed in a row" in (m.content or ""))
    assert note_at > max(i for i, m in enumerate(messages) if m.role == "tool")
    logs = [row["message"] for row in list_logs(stored["id"])]
    assert "run.orchestrator.toolThink" in logs
    # The direct fix answered everything; the safety net had nothing to do.
    assert "run.llm.toolCallsRepaired" not in logs


def test_close_open_tool_calls_fills_gaps_in_place() -> None:
    messages = [
        LlmMessage(role="system", content="s"),
        LlmMessage(role="assistant", content=None, tool_calls=_writes(3)),
        LlmMessage(role="tool", content="ok", tool_call_id="w0", name="file_access"),
        LlmMessage(role="user", content="note"),
        LlmMessage(role="assistant", content=None, tool_calls=_writes(1)),
    ]
    assert _close_open_tool_calls(messages) == 3
    roles = [(m.role, m.tool_call_id) for m in messages]
    assert roles == [
        ("system", None),
        ("assistant", None),
        ("tool", "w0"),
        ("tool", "w1"),
        ("tool", "w2"),
        ("user", None),
        ("assistant", None),
        ("tool", "w0"),
    ]
    _strict_openai_check(messages)


def test_close_open_tool_calls_leaves_complete_history_alone() -> None:
    messages = [
        LlmMessage(role="assistant", content=None, tool_calls=_writes(2)),
        LlmMessage(role="tool", content="a", tool_call_id="w1"),
        LlmMessage(role="tool", content="b", tool_call_id="w0"),
        LlmMessage(role="user", content="next"),
    ]
    before = [m.model_dump() for m in messages]
    assert _close_open_tool_calls(messages) == 0
    assert [m.model_dump() for m in messages] == before
