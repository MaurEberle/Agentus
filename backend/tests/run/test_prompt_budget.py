"""O7: the orchestrator prompt stays bounded and condenses instead of failing the run."""

from __future__ import annotations

from app.db.runs import list_logs
from app.run.memory import RunMemory
from app.run.window import WindowChoice
from app.runtime.models import CompletionRequest, CompletionResult
from tests.run.test_harness import _drive


def _prompt(memory: RunMemory) -> str:
    return "\n".join(m.content or "" for m in memory.orchestrator_messages("sys"))


def _finished(memory: RunMemory, agent_id: str, name: str, text: str):
    record = memory.begin_call(agent_id, name, "task", has_tools=False)
    record.text = text
    record.finished = True
    return record


def test_level_zero_bounds_notes_and_long_results() -> None:
    memory = RunMemory()
    memory.add_user("Bau mir etwas")
    for index in range(20):
        memory.add_note(f"note {index}")
    _finished(memory, "ag", "Schreiber", "A" * 50_000 + "ENDE")
    prompt = _prompt(memory)
    assert "note 11" not in prompt and "note 12" in prompt and "note 19" in prompt
    assert "Bau mir etwas" in prompt
    # Head and tail survive with a visible marker; the stored text is untouched.
    assert "ENDE" in prompt
    assert "characters of this result" in prompt and "set source to ag" in prompt
    assert len(prompt) < 25_000
    assert len(memory.records[0].text) == 50_004


def test_full_text_still_travels_as_source() -> None:
    memory = RunMemory()
    _finished(memory, "ag", "Schreiber", "B" * 30_000)
    memory.compact_level = 3
    source = memory.resolve_source("ag", [("ag", "Schreiber"), ("tr", "Translate")])
    message = memory.agent_message("tr", "übersetze", has_tools=False, source_text=source.text)
    assert message.count("B") >= 30_000


def test_higher_levels_condense_further() -> None:
    memory = RunMemory()
    memory.add_user("Start")
    for index in range(10):
        memory.add_spoken("reply", f"reply {index}")
        _finished(memory, f"a{index % 2}", f"Agent{index % 2}", "C" * 5_000)
    sizes = []
    for level in range(4):
        memory.compact_level = level
        sizes.append(len(_prompt(memory)))
    assert sizes == sorted(sizes, reverse=True) and sizes[3] < sizes[0]
    memory.compact_level = 3
    prompt = _prompt(memory)
    assert "Earlier calls, summarized:" in prompt
    assert "reply 9" in prompt and "reply 0" not in prompt
    assert "Start" in prompt


def test_run_condenses_instead_of_failing(monkeypatch, api_env) -> None:
    """A prompt above the window used to end the run with run.orchestrator.window."""
    from app.run import turn_runtime

    real_bind = turn_runtime._bind_window
    window_chars = 12_000

    def _bind(llm, messages, memory):
        choice = real_bind(llm, messages, memory)
        size = sum(len(m.content or "") for m in messages)
        return WindowChoice(num_ctx=choice.num_ctx, context_max=choice.context_max, fits=size <= window_chars)

    monkeypatch.setattr("app.run.turn_runtime._bind_window", _bind)
    orch_calls = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" not in system:
            return CompletionResult(content="D" * 15_000, model=req.model, finish_reason="stop")
        orch_calls["n"] += 1
        assert sum(len(m.content or "") for m in req.messages) <= window_chars
        if orch_calls["n"] == 1:
            content = '{"action":"call","agent":"Schreiber","task":"schreib viel"}'
        else:
            content = '{"action":"finish","text":"Fertig."}'
        return CompletionResult(content=content, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert "run.orchestrator.compact" in messages
    assert "run.orchestrator.window" not in messages
    assert stored["memory"]["compactLevel"] >= 1


def test_run_still_fails_when_nothing_fits(monkeypatch, api_env) -> None:
    def _bind(llm, messages, memory):
        return WindowChoice(num_ctx=None, context_max=100, fits=False)

    monkeypatch.setattr("app.run.turn_runtime._bind_window", _bind)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        raise AssertionError("no model call when nothing fits")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.orchestrator.window"
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert messages.count("run.orchestrator.compact") == 3
