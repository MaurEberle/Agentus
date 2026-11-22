"""The orchestrator sees the course of its calls (run bd3cfb0f, 2026-11-21).

The coder rewrote the CSS in its first call. Later decisions showed only its newest
result ("nothing missing"), the last eight file lines of each call (node_modules reads,
the SCSS writes cut off) and no task. Five calls repeated work already done, then the
orchestrator asked the user what was still broken, in a reply and again as ask.
"""

from __future__ import annotations

import time

from app.db.runs import list_logs
from app.run.memory import FileFact, RunMemory
from app.run.orchestrate import asks_user
from app.run.previous_run import _clip_lines
from app.runtime.models import CompletionRequest, CompletionResult


def _prompt(memory: RunMemory) -> str:
    return "\n".join(message.content or "" for message in memory.orchestrator_messages("sys"))


def _bd3c_memory() -> RunMemory:
    memory = RunMemory()
    memory.add_user("das CSS wurde kaputt gemacht und muss neu implementiert werden")
    work = memory.begin_call("coder", "Coder", "Die SCSS-Dateien sind fast leer und müssen befüllt werden.", True)
    work.text = "All tasks are complete. _layout.scss was 85 bytes, now 2577 bytes. " + "Details. " * 200
    work.finished = True
    for path, size in (("src/modules/_layout.scss", 2577), ("src/modules/_components.scss", 5488)):
        work.files.append(FileFact("file_access", "write", path, True, size))
    work.files.append(FileFact("file_access", "write", "check.mjs", True, 400))
    work.files.append(FileFact("file_access", "delete", "check.mjs", True))
    for index in range(7):
        work.files.append(FileFact("file_access", "read", f"node_modules/sass/f{index}.js", True, 100))
    work.files.append(FileFact("file_access", "search", "node_modules/sass", False))
    # Seen in the run: a malformed call with markup as its action.
    work.files.append(FileFact("file_access", "stat>\n<parameter=path>\ndist/a.css", "", True))
    work.files.append(FileFact("file_access", "edit", "node_modules/vite-plugin-sass/index.js", True, 854))
    review = memory.begin_call("rev", "Reviewer", "Prüfe die SCSS-Dateien.", True)
    review.text = "MÄNGEL: detail-description fehlt."
    review.finished = True
    check = memory.begin_call("coder", "Coder", "Behebe die Mängel aus dem Review.", True)
    check.text = "Fehlende Klassen: 0 — keine Klassen mussten hinzugefügt werden."
    check.finished = True
    check.files.append(FileFact("file_access", "read", "src/modules/_components.scss", True, 5488))
    return memory


def test_status_lines_carry_task_changes_and_the_start_of_earlier_results() -> None:
    prompt = _prompt(_bd3c_memory())
    assert "Agent calls in this run, oldest first:" in prompt
    assert "Call 1: Agent Coder (coder) finished." in prompt
    assert "task: Die SCSS-Dateien sind fast leer" in prompt
    assert "Call 3: Agent Coder (coder) finished." in prompt and "task: Behebe die Mängel" in prompt
    # Changed files first, each path once with its last change; reads only counted.
    assert "src/modules/_layout.scss write ok 2577" in prompt
    assert "src/modules/_components.scss write ok 5488" in prompt
    assert "check.mjs delete ok" in prompt and "check.mjs write" not in prompt
    assert "node_modules/vite-plugin-sass/index.js edit ok 854" in prompt
    assert "other file actions: read 7, search 1, other 1 (1 failed)" in prompt
    assert "<parameter=path>" not in prompt
    assert "node_modules/sass/f0.js" not in prompt
    # The first coder report is no longer shown in full, but its start is.
    assert "start of its result (a later call of this agent is shown in full):" in prompt
    assert '<agent_result agent="Coder" id="coder" call="1">\nAll tasks are complete. _layout.scss was 85 bytes' in prompt
    assert prompt.count("Details.") < 60
    # The latest result per agent stays in full, with its call number.
    assert '<agent_result agent="Coder" id="coder" call="3">\nFehlende Klassen: 0' in prompt
    assert '<agent_result agent="Reviewer" id="rev" call="2">\nMÄNGEL' in prompt
    assert prompt.count("start of its result") == 1


def test_a_shortened_prompt_keeps_tasks_and_changed_files() -> None:
    memory = _bd3c_memory()
    full = _prompt(memory)
    # The first step removes the start of the replaced coder result, nothing else.
    assert memory.compact_step() == "olderResult"
    first = _prompt(memory)
    assert "All tasks are complete" not in first and len(first) < len(full)
    assert "result: removed from this prompt for space; a later call of this agent replaced it." in first
    assert "MÄNGEL: detail-description fehlt." in first
    while memory.compact_step() is not None:
        pass
    last = _prompt(memory)
    # Tasks (shortened) and changed files of every call are still there.
    assert "task: Die SCSS-Dateien sind fast leer" in last and "task: Behebe die Mängel" in last
    assert "src/modules/_layout.scss write ok 2577" in last
    assert "node_modules/vite-plugin-sass/index.js edit ok 854" in last
    # The reviewer result was older than the newest one: removed, with the way to pass it on.
    assert "MÄNGEL: detail-description" not in last
    assert "set source to rev to pass the full text" in last
    assert "Fehlende Klassen: 0" in last


def test_a_question_in_a_reply_is_found() -> None:
    asked = (
        "Ich habe das Problem verstanden.\n\n**Was konkret ist am CSS kaputt?** Bitte beschreibe es.\n"
        "- Welche Klassen haben falsche Eigenschaften?\n"
    )
    assert asks_user(asked)
    assert asks_user("Soll ich den Reviewer noch einmal prüfen lassen?")
    assert asks_user("¿Qué falta todavía?»")
    assert not asks_user("Der Coder hat das CSS geschrieben. Ich lasse es jetzt prüfen.")
    assert not asks_user("Was ist passiert? Der Build schlug fehl, der Coder behebt es.")
    assert not asks_user("Beispiel:\n```js\nconst ok = a ? b : c ?\n```\nDer Coder baut weiter.")


def test_the_briefing_is_cut_at_a_line_end() -> None:
    text = "## Offen\n" + "- Punkt mit Text\n" * 30 + "Die SCSS-Dateien müssen definiert werden."
    clipped = _clip_lines(text, 200)
    assert len(clipped) <= 200 and clipped.endswith("\n…")
    assert clipped[:-2].endswith("- Punkt mit Text")
    words = _clip_lines("wort " * 100, 50)
    assert len(words) <= 50 and words.endswith(" …") and "wor …" not in words
    assert _clip_lines("kurz", 50) == "kurz"


def test_a_reply_with_a_question_waits_for_the_answer(monkeypatch, api_env) -> None:
    from app.db import init
    from app.db.engine import utc_now
    from app.db.networks import NetworkRow, upsert_network
    from app.db.runs import get_run
    from app.run.controller import get_controller
    from app.settings.models import AppSettingsPatch
    from app.settings.service import patch_settings
    from tests.run.test_validate import _orchestrator_doc

    init()
    prompts: list[str] = []
    question = "Der Coder meldet: alles da.\n**Was genau ist noch kaputt?**\n- Layout?\n- Animation?"

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if "You orchestrate" not in (req.messages[0].content or ""):
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        prompts.append("\n".join(message.content or "" for message in req.messages))
        if len(prompts) == 1:
            return CompletionResult(content='{"action":"reply","text":' + _json(question) + "}", model=req.model, finish_reason="stop")
        assert "Nichts mehr, es läuft." in prompts[-1]
        return CompletionResult(content='{"action":"finish","text":"Gut, dann schließe ich."}', model=req.model, finish_reason="stop")

    monkeypatch.setattr("app.runtime.completions.complete_live", _complete)
    upsert_network(
        NetworkRow(
            id="net-1",
            name="mini",
            description=None,
            tags=[],
            document=_orchestrator_doc(),
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    patch_settings(AppSettingsPatch(active_network_id="net-1"))
    ctrl = get_controller()
    started = ctrl.start()
    ctrl.chat_input_queue.put("Prüfe das CSS.")
    deadline = time.monotonic() + 5
    while ctrl._wait_ask is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert ctrl._wait_ask is not None
    ctrl.chat_input_queue.put("Nichts mehr, es läuft.")
    assert ctrl.thread is not None
    ctrl.thread.join(timeout=5)
    assert ctrl.thread.is_alive() is False
    stored = get_run(started["runId"])
    assert stored is not None and stored["outcome"] == "succeeded", stored and stored.get("error_message")
    texts = [item["content"] for item in stored["chat"] or [] if item.get("role") == "assistant"]
    # Once in the chat, and the run waited for the answer before it decided again.
    assert texts.count(question) == 1 and len(prompts) == 2
    messages = [row["message"] for row in list_logs(started["runId"])]
    assert "run.orchestrator.replyAsAsk" in messages and "run.wait.ask" in messages
    actions = [row["payload"]["action"] for row in list_logs(started["runId"]) if row["message"] == "run.orchestrator.action"]
    assert actions == ["ask", "finish"]


def _json(text: str) -> str:
    import json

    return json.dumps(text, ensure_ascii=False)
