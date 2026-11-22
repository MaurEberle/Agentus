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


def _cut_all(memory: RunMemory) -> list[str]:
    cuts = []
    while (cut := memory.compact_step()) is not None:
        cuts.append(cut)
    return cuts


def test_full_text_still_travels_as_source() -> None:
    memory = RunMemory()
    _finished(memory, "ag", "Schreiber", "B" * 30_000)
    _cut_all(memory)
    source = memory.resolve_source("ag", [("ag", "Schreiber"), ("tr", "Translate")])
    message = memory.agent_message("tr", "übersetze", has_tools=False, source_text=source.text)
    assert message.count("B") >= 30_000


def test_steps_cut_the_oldest_results_first_and_keep_every_task() -> None:
    """Run bd3cfb0f, 2026-11-22: the old level 2 dropped every task; now they stay."""
    memory = RunMemory()
    memory.add_user("Start")
    for index in range(6):
        memory.add_spoken("reply", f"reply {index}")
        record = _finished(memory, f"a{index % 3}", f"Agent{index % 3}", f"R{index}-" + "C" * 5_000)
        record.task = f"Aufgabe {index}: " + "t" * 300
    sizes = [len(_prompt(memory))]
    cuts = []
    while (cut := memory.compact_step()) is not None:
        cuts.append(cut)
        sizes.append(len(_prompt(memory)))
    # Calls 1-3 were replaced by calls 4-6: their starts go first, oldest first.
    assert cuts[:3] == ["olderResult"] * 3
    # Then the latest results except the newest (call 6): calls 4 and 5 to their start, then away.
    assert cuts[3:7] == ["resultStart", "resultStart", "result", "result"]
    assert cuts[7:] == ["course", "course", "course", "newestResult", "newestResult", "tasks", "user", "user", "toolResults"]
    assert sizes == sorted(sizes, reverse=True) and sizes[-1] < sizes[0] // 3
    assert memory.compact_steps == len(cuts)
    prompt = _prompt(memory)
    # Every call keeps its line and task, shortened; the user message stays.
    for index in range(6):
        assert f"Call {index + 1}: Agent" in prompt and f"task: Aufgabe {index}: " in prompt
    assert "t" * 120 not in prompt
    assert "Start" in prompt
    assert "Earlier calls, summarized" not in prompt
    # Removed results say so and how to pass them on; the newest result is still there, cut.
    assert "result: removed from this prompt for space; a later call of this agent replaced it." in prompt
    assert "result: removed from this prompt for space; set source to a1 to pass the full text." in prompt
    assert "R5-" in prompt and "R4-" not in prompt and "R0-" not in prompt
    assert "reply 5" in prompt and "reply 0" not in prompt


def test_one_step_at_a_time_keeps_the_newest_result_whole() -> None:
    memory = RunMemory()
    for index in range(3):
        _finished(memory, f"a{index}", f"Agent{index}", f"R{index}-" + "D" * 3_000)
    assert memory.compact_step() == "resultStart"
    prompt = _prompt(memory)
    # Only the oldest latest result is cut to its start; the others stay whole.
    assert "only the start is shown" in prompt and prompt.count("only the start is shown") == 1
    assert "R1-" + "D" * 2_900 in prompt and "R2-" + "D" * 2_900 in prompt
    assert "R0-" + "D" * 1_000 not in prompt


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
    logs = list_logs(stored["id"])
    messages = [row["message"] for row in logs]
    assert "run.orchestrator.trimmed" in messages
    assert "run.orchestrator.window" not in messages
    trimmed = [row["payload"] for row in logs if row["message"] == "run.orchestrator.trimmed"]
    assert trimmed[0]["steps"] >= 1 and trimmed[-1]["total"] == stored["memory"]["compactSteps"]


def test_run_still_fails_when_nothing_fits(monkeypatch, api_env) -> None:
    def _bind(llm, messages, memory):
        return WindowChoice(num_ctx=None, context_max=100, fits=False)

    monkeypatch.setattr("app.run.turn_runtime._bind_window", _bind)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        raise AssertionError("no model call when nothing fits")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.orchestrator.window"
    logs = list_logs(stored["id"])
    trimmed = [row["payload"] for row in logs if row["message"] == "run.orchestrator.trimmed"]
    # One line for the decision, after every step was tried.
    assert len(trimmed) == 1 and trimmed[0]["cuts"][-1] == "toolResults"
