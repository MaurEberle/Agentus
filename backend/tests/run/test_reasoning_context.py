"""Reasoning goes back to local models, runtime notes stay at the tool result, context watch.

Investigation 2026-11-21: the agent planned in its reasoning (771 characters per step)
and lost it after every step; Ollama 0.40 ignores the thinking field of earlier messages
but reads it inside the content.
"""

from __future__ import annotations

from app.db.runs import list_logs
from app.run.context_watch import ContextWatch
from app.runtime.completions import _ollama_messages, _openai_messages, _payload
from app.runtime.models import ChatMessage, CompletionRequest, CompletionResult, CompletionUsage, ToolCall


def _assistant() -> ChatMessage:
    return ChatMessage(
        role="assistant",
        content="",
        tool_calls=[ToolCall(id="t", name="terminal", arguments='{"command": "npm run build"}')],
        reasoning="grep is not allowed; I use file_access search with text.",
    )


def test_local_models_get_the_reasoning_inside_the_content() -> None:
    messages = [ChatMessage(role="user", content="Prüfe."), _assistant()]
    ollama = _ollama_messages(messages)
    assert ollama[1]["content"] == "<think>\ngrep is not allowed; I use file_access search with text.\n</think>"
    assert "thinking" not in ollama[1]
    compat = _payload(CompletionRequest(provider="openai_compat", model="m", messages=messages), stream=False)
    assert compat["messages"][1]["content"].startswith("<think>\ngrep is not allowed")
    for provider in ("openai", "xai"):
        cloud = _payload(CompletionRequest(provider=provider, model="m", messages=messages), stream=False)
        body = str(cloud.get("messages") or cloud.get("input"))
        assert "grep is not allowed" not in body, provider
    assert _openai_messages(messages)[1]["content"] == ""


def test_context_watch_finds_drops_and_the_edge() -> None:
    watch = ContextWatch()
    assert watch.observe(reported=10_000, estimate=9_000, context_max=200_000) is None
    assert watch.observe(reported=12_000, estimate=11_000, context_max=200_000) is None
    # The transcript only grows within a call: a clear fall means tokens were lost.
    cut = watch.observe(reported=8_000, estimate=13_000, context_max=200_000)
    assert cut == {"reason": "drop", "reported": 8_000, "expected": 12_000, "contextMax": 200_000}
    # After a compaction a smaller prompt is expected.
    watch.compacted()
    assert watch.observe(reported=5_000, estimate=5_000, context_max=200_000) is None
    # Small changes are not a cut (estimate error, a replaced think).
    assert watch.observe(reported=4_400, estimate=5_000, context_max=200_000) is None
    edge = ContextWatch(detect_drops=False)
    assert edge.observe(reported=8_192, estimate=30_000, context_max=32_768) == {
        "reason": "edge",
        "reported": 8_192,
        "expected": 30_000,
        "contextMax": 32_768,
    }
    assert edge.observe(reported=4_000, estimate=8_000, context_max=200_000) is None
    assert watch.payload() == {
        "promptMax": 12_000,
        "compactions": 1,
        "contextCuts": 1,
        "contextMax": 200_000,
        "contextShare": 6.0,
    }


def test_the_agent_gets_its_reasoning_back_and_notes_stay_at_the_tool_result(monkeypatch, api_env) -> None:
    from tests.run.test_harness import _drive
    from tests.run.test_validate import _orchestrator_doc

    doc = _orchestrator_doc()
    doc["nodes"].append(
        {"id": "files", "type": "tool", "position": {"x": 0, "y": 0}, "data": {"kind": "file_access", "rootPath": "C:/p"}}
    )
    doc["edges"].append({"id": "ef", "source": "files", "sourceHandle": "tool", "target": "ag", "targetHandle": "tool"})
    # Two tool calls per task, then the runtime note about the limit.
    next(node for node in doc["nodes"] if node["id"] == "ag")["data"]["maxToolCalls"] = 2
    seen: list[list[ChatMessage]] = []
    sizes = iter([3_000, 4_000, 1_500, 1_600])
    orch = {"n": 0}

    def _execute(kind, *, config, args, secret=None):
        from app.tools.models import ExecuteResult

        return ExecuteResult(ok=True, result={"path": ".", "entries": ["a.css"]})

    monkeypatch.setattr("app.run.turn_runtime.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if "You orchestrate" in (req.messages[0].content or ""):
            orch["n"] += 1
            if orch["n"] == 1:
                return CompletionResult(content='{"action":"call","agent":"Schreiber","task":"Prüfe."}', model="m")
            return CompletionResult(content='{"action":"finish","text":"Fertig."}', model="m")
        seen.append(list(req.messages))
        usage = CompletionUsage(promptTokens=next(sizes, 1_700), completionTokens=10)
        if len(seen) <= 2:
            return CompletionResult(
                content=None,
                reasoning=f"Schritt {len(seen)}: ich liste den Ordner.",
                tool_calls=[ToolCall(id=f"c{len(seen)}", name="file_access", arguments=f'{{"action":"list","path":"d{len(seen)}"}}')],
                usage=usage,
                model="m",
                finish_reason="tool_calls",
            )
        return CompletionResult(content="Geprüft.", usage=usage, model="m", finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "succeeded", stored.get("error_message")
    second, third = seen[1], seen[2]
    # 1: the reasoning of the first step is on its assistant message in the next request.
    assistants = [message for message in second if message.role == "assistant"]
    assert assistants[-1].reasoning == "Schritt 1: ich liste den Ordner."
    # 2: the limit note is part of the last tool result, not a user message after it.
    assert third[-1].role == "tool" and "Note from the runtime:" in (third[-1].content or "")
    assert [message.role for message in third[-3:]] == ["tool", "assistant", "tool"]
    # 3: the prompt fell from 4000 to 1500 tokens without compaction: a likely cut.
    logs = list_logs(stored["id"])
    cuts = [row["payload"] for row in logs if row["message"] == "run.llm.contextCut"]
    assert [(cut["reason"], cut["reported"], cut["expected"]) for cut in cuts] == [("drop", 1_500, 4_000)]
    done = [row["payload"] for row in logs if row["message"] == "run.agent.done"][0]
    assert done["promptMax"] == 4_000 and done["contextCuts"] == 1
    starts = [row["payload"] for row in logs if row["message"] == "run.llm.start" and row["payload"].get("caller") == "ag"]
    assert all(isinstance(item.get("promptEst"), int) for item in starts)
    summary = [row["payload"] for row in logs if row["message"] == "run.summary"][0]
    assert summary["limits"].get("run.llm.contextCut") == 1


def test_only_the_latest_steps_keep_their_reasoning() -> None:
    from app.run.agent_turn import _drop_reasoning, _kept_reasoning, _prune_reasoning
    from app.run.limits import REASONING_CHARS, REASONING_STEPS_KEPT

    messages = [ChatMessage(role="system", content="s")]
    for index in range(REASONING_STEPS_KEPT + 3):
        messages.append(ChatMessage(role="assistant", content="", reasoning=f"r{index}"))
        messages.append(ChatMessage(role="tool", content="ok"))
    _prune_reasoning(messages)
    kept = [message.reasoning for message in messages if message.reasoning]
    assert kept == [f"r{index}" for index in range(3, REASONING_STEPS_KEPT + 3)]
    assert len(_kept_reasoning("x" * 5000) or "") <= REASONING_CHARS + 40
    assert _kept_reasoning("  ") is None
    assert _drop_reasoning(messages) is True and not any(message.reasoning for message in messages)
