from __future__ import annotations

from app.runtime.models import CompletionRequest, CompletionResult, CompletionUsage
from tests.run.conftest import mini_doc


def test_orchestrator_asks_calls_and_finishes(monkeypatch, api_env) -> None:
    from app.db import init
    from app.db.engine import utc_now
    from app.db.networks import NetworkRow, upsert_network
    from app.db.runs import get_run
    from app.run.controller import get_controller
    from app.settings.models import AppSettingsPatch
    from app.settings.service import patch_settings
    from tests.run.test_validate import _orchestrator_doc

    init()
    calls: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content
        calls.append(system)
        if "You orchestrate" in system:
            step = sum(1 for item in calls if "You orchestrate" in item)
            if step == 1:
                return CompletionResult(
                    content='{"action":"ask","text":"Welche Sprache?"}',
                    model=req.model,
                    finish_reason="stop",
                )
            if step == 2:
                return CompletionResult(
                    content='{"action":"call","agent":"Schreiber","task":"schreib"}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"finish","text":"Fertig."}',
                model=req.model,
                finish_reason="stop",
            )
        joined = "\n".join(message.content or "" for message in req.messages)
        assert "schreib" in joined
        return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")

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
    ctrl.chat_input_queue.put("Hallo")
    ctrl.chat_input_queue.put("Deutsch")
    assert ctrl.thread is not None
    ctrl.thread.join(timeout=5)
    assert ctrl.thread.is_alive() is False
    stored = get_run(started["runId"])
    assert stored is not None
    assert stored["outcome"] == "succeeded"
    chat = stored["chat"] or []
    texts = [item["content"] for item in chat]
    assert "Welche Sprache?" in texts
    assert "Fertig." in texts
    assert "agent-text" not in texts
    from app.db.runs import list_logs

    waits = [row for row in list_logs(started["runId"]) if row["message"] == "run.wait.human"]
    assert len(waits) == 2
    asks = [row for row in list_logs(started["runId"]) if row["message"] == "run.wait.ask"]
    assert len(asks) == 1
    payload = asks[0].get("payload") or {}
    assert payload.get("excerpt") == "Welche Sprache?"
    assert payload.get("speaker")


def test_orchestrator_reply_continues_without_waiting(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs

    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" not in system:
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        prompts.append(blob)
        orch_n = sum(1 for item in prompts if "You orchestrate" in item)
        if orch_n == 1:
            return CompletionResult(
                content='{"action":"reply","text":"Ich lasse den Autor schreiben."}',
                model=req.model,
                finish_reason="stop",
            )
        if orch_n == 2:
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"schreib"}',
                model=req.model,
                finish_reason="stop",
            )
        return CompletionResult(
            content='{"action":"finish","text":"Fertig."}',
            model=req.model,
            finish_reason="stop",
        )

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Ich lasse den Autor schreiben." in texts
    assert "Fertig." in texts
    assert "agent-text" not in texts
    waits = [row for row in list_logs(stored["id"]) if row["message"] == "run.wait.human"]
    assert len(waits) == 1
    assert "Ich lasse den Autor schreiben." in prompts[1]


def test_orchestrator_runs_a_truncated_call_without_showing_it(monkeypatch, api_env) -> None:
    from app.db import init
    from app.db.engine import utc_now
    from app.db.networks import NetworkRow, upsert_network
    from app.db.runs import get_run
    from app.run.controller import get_controller
    from app.settings.models import AppSettingsPatch
    from app.settings.service import patch_settings
    from tests.run.test_validate import _orchestrator_doc

    init()
    seen: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            step = sum(1 for item in seen if item == "orch")
            seen.append("orch")
            if step == 0:
                return CompletionResult(
                    content='{"action":"call","agent":"Schreiber","task":"schreib eine geschichte.","',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"finish","text":"Fertig."}',
                model=req.model,
                finish_reason="stop",
            )
        seen.append("agent")
        joined = "\n".join(message.content or "" for message in req.messages)
        assert "schreib eine geschichte." in joined
        return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")

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
    ctrl.chat_input_queue.put("Hallo")
    assert ctrl.thread is not None
    ctrl.thread.join(timeout=5)
    assert "agent" in seen
    stored = get_run(started["runId"])
    assert stored is not None
    assert stored["outcome"] == "succeeded"
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Fertig." in texts
    assert all("action" not in item for item in texts)


def test_execute_first_party_allowlist(monkeypatch, api_env) -> None:
    from app.db import init
    from app.db.engine import utc_now
    from app.db.networks import NetworkRow, upsert_network
    from app.run.controller import get_controller
    from app.settings.models import AppSettingsPatch
    from app.settings.service import patch_settings

    init()
    called: list[str] = []

    def _exec(kind, **kwargs):
        called.append(kind)
        from app.tools.models import ExecuteResult

        return ExecuteResult(ok=True, result={"value": 1})

    monkeypatch.setattr("app.tools.execute.execute_first_party", _exec)

    def _complete(req: CompletionRequest) -> CompletionResult:
        from app.runtime.models import ToolCall

        if not any(m.role == "tool" for m in req.messages):
            return CompletionResult(
                content=None,
                model=req.model,
                tool_calls=[
                    ToolCall(id="1", name="calculator", arguments='{"expression":"1+1"}')
                ],
            )
        return CompletionResult(content="done", model=req.model, finish_reason="stop")

    monkeypatch.setattr(
        "app.runtime.completions.complete_live",
        lambda req, should_abort=None, on_progress=None: _complete(req),
    )
    monkeypatch.setattr("app.tools.execute.execute_first_party", _exec)
    doc = mini_doc(startMessage="go")
    doc["nodes"].append(
        {
            "id": "calc",
            "type": "tool",
            "position": {"x": 0, "y": 0},
            "data": {"kind": "calculator"},
        }
    )
    doc["edges"].append(
        {
            "id": "et",
            "source": "calc",
            "sourceHandle": "tool",
            "target": "ag",
            "targetHandle": "tool",
        }
    )
    upsert_network(
        NetworkRow(
            id="net-1",
            name="mini",
            description=None,
            tags=[],
            document=doc,
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    patch_settings(AppSettingsPatch(active_network_id="net-1"))
    run_id = get_controller().start()["runId"]
    thread = get_controller().thread
    if thread:
        thread.join(timeout=5)
    assert "calculator" in called
    assert "http" not in called
    from app.db.runs import list_logs

    messages = [row["message"] for row in list_logs(run_id)]
    assert "run.tool.call" in messages


def _drive(monkeypatch, complete, *, doc=None, user_texts=("Hallo",)):
    from app.db import init
    from app.db.engine import utc_now
    from app.db.networks import NetworkRow, upsert_network
    from app.db.runs import get_run
    from app.run.controller import get_controller
    from app.settings.models import AppSettingsPatch
    from app.settings.service import patch_settings
    from tests.run.test_validate import _orchestrator_doc

    init()
    monkeypatch.setattr("app.runtime.completions.complete_live", complete)
    upsert_network(
        NetworkRow(
            id="net-1",
            name="mini",
            description=None,
            tags=[],
            document=doc or _orchestrator_doc(),
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    patch_settings(AppSettingsPatch(active_network_id="net-1"))
    ctrl = get_controller()
    started = ctrl.start()
    for text in user_texts:
        ctrl.chat_input_queue.put(text)
    assert ctrl.thread is not None
    ctrl.thread.join(timeout=5)
    assert ctrl.thread.is_alive() is False
    stored = get_run(started["runId"])
    assert stored is not None
    return stored


def test_agent_timeout_lets_the_orchestrator_finish(monkeypatch, api_env) -> None:
    from app.runtime.errors import RuntimeApiError

    agent_calls = {"n": 0}
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            prompts.append("\n".join(message.content or "" for message in req.messages))
            if len(prompts) == 1:
                return CompletionResult(
                    content='{"action":"call","agent":"Schreiber","task":"schreib"}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"finish","text":"Fertig."}',
                model=req.model,
                finish_reason="stop",
            )
        agent_calls["n"] += 1
        raise RuntimeApiError("runtime.timeout")

    stored = _drive(monkeypatch, _complete)
    assert agent_calls["n"] == 2
    assert stored["outcome"] == "succeeded"
    assert "runtime.timeout" in prompts[1]
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Fertig." in texts
    assert "Ich konnte den nächsten Schritt nicht lesen" not in "\n".join(texts)
    assert "is done" not in "\n".join(texts)


def test_three_unreadable_jsons_fail_without_asking(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs

    garbage = "{nicht-json CALL Senior"
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        prompts.append("\n".join(message.content or "" for message in req.messages))
        return CompletionResult(content=garbage, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.orchestrator.unreadable"
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert garbage not in "\n".join(texts)
    assert all(garbage not in item for item in prompts)
    rejected = (stored["memory"] or {}).get("rejected") or []
    assert len(rejected) == 3
    assert all(item["reason"] == "unreadable" for item in rejected)
    repairs = [row for row in list_logs(stored["id"]) if row["message"] == "run.orchestrator.repair"]
    assert len(repairs) == 3
    payload = repairs[0].get("payload") or {}
    assert payload.get("reason") == "unreadable"
    assert garbage in (payload.get("body") or "")


def test_prose_call_runs_the_agent(monkeypatch, api_env) -> None:
    seen: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            seen.append("orch")
            if seen.count("orch") == 1:
                return CompletionResult(
                    content='Call Schreiber with the full German story under the title "Der Tiger".',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"finish","text":"Fertig."}',
                model=req.model,
                finish_reason="stop",
            )
        seen.append("agent")
        joined = "\n".join(message.content or "" for message in req.messages)
        assert "Tiger" in joined
        return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    assert seen.count("agent") == 1
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Call Schreiber" not in "\n".join(texts)
    assert "Fertig." in texts
    assert "Schreiber is done." in texts


def test_unreadable_after_reply_does_not_fail_the_run(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs

    orch_n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" not in system:
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        orch_n["n"] += 1
        if orch_n["n"] == 1:
            return CompletionResult(
                content='{"action":"reply","text":"Scaffold steht."}',
                model=req.model,
                finish_reason="stop",
            )
        if orch_n["n"] <= 4:
            return CompletionResult(content="{nicht-json", model=req.model, finish_reason="stop")
        return CompletionResult(
            content='{"action":"finish","text":"Fertig."}',
            model=req.model,
            finish_reason="stop",
        )

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Scaffold steht." in texts
    assert "Fertig." in texts
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert "run.orchestrator.think" in messages
    assert "run.orchestrator.unreadable" not in messages


def test_reasoning_only_json_calls_the_agent(monkeypatch, api_env) -> None:
    seen: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            seen.append("orch")
            if seen.count("orch") == 1:
                return CompletionResult(
                    content=None,
                    reasoning='{"action":"call","agent":"Schreiber","task":"schreib"}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"finish","text":"Fertig."}',
                model=req.model,
                finish_reason="stop",
            )
        seen.append("agent")
        return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    assert seen.count("agent") == 1
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Fertig." in texts
    assert "Schreiber is done." in texts


def test_orchestrator_step_limit_is_stored(monkeypatch, api_env) -> None:
    monkeypatch.setattr("app.run.harness.MAX_ORCHESTRATOR_STEPS", 2)
    orch_n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            orch_n["n"] += 1
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"schreib"}',
                model=req.model,
                finish_reason="stop",
            )
        return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.stepLimit"
    assert stored["error_class"] == "orchestrator"
    assert orch_n["n"] == 3


def test_think_does_not_consume_the_step_limit(monkeypatch, api_env) -> None:
    monkeypatch.setattr("app.run.harness.MAX_ORCHESTRATOR_STEPS", 2)
    orch_n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            orch_n["n"] += 1
            if orch_n["n"] == 1:
                return CompletionResult(
                    content='{"action":"reply","text":"Scaffold steht."}',
                    model=req.model,
                    finish_reason="stop",
                )
            if orch_n["n"] <= 6:
                return CompletionResult(
                    content="Ich prüfe den Dateistand und plane den nächsten Auftrag.",
                    model=req.model,
                    finish_reason="stop",
                )
            if orch_n["n"] == 7:
                return CompletionResult(
                    content='{"action":"call","agent":"Schreiber","task":"schreib"}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"finish","text":"Fertig."}',
                model=req.model,
                finish_reason="stop",
            )
        return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    from app.db.runs import list_logs

    messages = [row["message"] for row in list_logs(stored["id"])]
    assert messages.count("run.orchestrator.think") == 5
    assert "run.stepLimit" not in messages
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Scaffold steht." in texts
    assert "Ich prüfe den Dateistand" not in "\n".join(texts)
    assert "Fertig." in texts


def test_think_limit_is_stored(monkeypatch, api_env) -> None:
    monkeypatch.setattr("app.run.harness.MAX_ORCHESTRATOR_THINKS", 2)
    orch_n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            orch_n["n"] += 1
            if orch_n["n"] == 1:
                return CompletionResult(
                    content='{"action":"reply","text":"Scaffold steht."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content="Ich prüfe den Dateistand.",
                model=req.model,
                finish_reason="stop",
            )
        return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.orchestrator.thinkLimit"
    assert stored["error_class"] == "orchestrator"
    assert orch_n["n"] == 3


def test_orchestrator_one_token_think_loop_fails_the_run(monkeypatch, api_env) -> None:
    orch_n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            orch_n["n"] += 1
            return CompletionResult(
                content='{"action":"think","text":"."}',
                usage=CompletionUsage(prompt_tokens=32, completion_tokens=1),
                model=req.model,
                finish_reason="stop",
            )
        return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.orchestrator.thinkLoop"
    assert stored["error_class"] == "orchestrator"
    assert orch_n["n"] == 5
    from app.db.runs import list_logs

    messages = [row["message"] for row in list_logs(stored["id"])]
    assert messages.count("run.orchestrator.think") == 5
    assert "run.orchestrator.thinkLoop" in messages
    assert "run.orchestrator.thinkLimit" not in messages


def test_orchestrator_prompt_contains_the_last_agent_result(monkeypatch, api_env) -> None:
    manuscript = "EINMALIGES-MANUSKRIPT-9f3a"
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            prompts.append("\n".join(message.content or "" for message in req.messages))
            if len(prompts) == 1:
                return CompletionResult(
                    content='{"action":"call","agent":"Schreiber","task":"schreib"}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"finish","text":"Fertig."}',
                model=req.model,
                finish_reason="stop",
            )
        return CompletionResult(content=manuscript, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    assert manuscript in prompts[1]
    assert "Result from Schreiber" in prompts[1]
    assert f"characters: {len(manuscript)}" in prompts[1]
    assert stored["memory"]["calls"][0]["text"] == manuscript
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert manuscript not in "\n".join(texts)
    assert "Schreiber is done." in texts
    done = next(item for item in stored["chat"] if item["content"] == "Schreiber is done.")
    assert done["messageKey"] == "monitoring.chat.agentDone"
    assert done["messageParams"]["name"] == "Schreiber"


def test_next_text_agent_receives_the_writer_result(monkeypatch, api_env) -> None:
    from tests.run.test_validate import _orchestrator_doc

    manuscript = "TIGER-GESCHICHTE-9f3a"
    agent_prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            if "Result from Translate" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            if "Result from Schreiber" in blob:
                return CompletionResult(
                    content='{"action":"call","agent":"Translate","task":"übersetze"}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"schreib"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_prompts.append(blob)
        if "Source text" in blob:
            return CompletionResult(content="DE/EN/ES", model=req.model, finish_reason="stop")
        return CompletionResult(content=manuscript, model=req.model, finish_reason="stop")

    doc = _orchestrator_doc()
    doc["nodes"].append(
        {
            "id": "tr",
            "type": "agent",
            "position": {"x": 0, "y": 0},
            "data": {"displayName": "Translate", "systemPrompt": "trans"},
        }
    )
    doc["edges"].extend(
        [
            {
                "id": "e6",
                "source": "llm",
                "sourceHandle": "llm",
                "target": "tr",
                "targetHandle": "llm",
            },
            {
                "id": "e7",
                "source": "orch",
                "sourceHandle": "channel:tr",
                "target": "tr",
                "targetHandle": "channel",
            },
        ]
    )
    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "succeeded"
    assert any(manuscript in item and "Source text" in item for item in agent_prompts)
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert manuscript not in "\n".join(texts)
    assert "Fertig." in texts


def test_orchestrator_calls_a_connected_tool_without_keeping_the_result(monkeypatch, api_env) -> None:
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult
    from tests.run.test_validate import _orchestrator_doc

    raw_listing = "ROHER-LISTE-9f3a"
    prompts: list[str] = []
    seen_tools: list[object] = []

    def _execute(kind, *, config, args, secret=None):
        assert kind == "file_access"
        assert args.get("action") == "list"
        return ExecuteResult(ok=True, result={"path": ".", "entries": [raw_listing]})

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" not in system:
            prompts.append(blob)
            return CompletionResult(content="kurz", model=req.model, finish_reason="stop")
        prompts.append(blob)
        seen_tools.append(req.tools)
        orch_n = sum(1 for item in prompts if "You orchestrate" in item)
        if orch_n == 1:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name="file_access", arguments='{"action":"list","path":"."}')
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        if orch_n == 2:
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"schreib"}',
                model=req.model,
                finish_reason="stop",
            )
        return CompletionResult(
            content='{"action":"finish","text":"Fertig."}',
            model=req.model,
            finish_reason="stop",
        )

    doc = _orchestrator_doc()
    doc["nodes"].append(
        {
            "id": "files",
            "type": "tool",
            "position": {"x": 0, "y": 0},
            "data": {"kind": "file_access", "rootPath": "C:/stories"},
        }
    )
    doc["edges"].append(
        {
            "id": "et",
            "source": "files",
            "sourceHandle": "tool",
            "target": "orch",
            "targetHandle": "tool",
        }
    )
    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "succeeded"
    assert seen_tools[0] and any(
        (item.get("function") or {}).get("name") == "file_access" for item in seen_tools[0]
    )
    assert len(prompts) == 4
    assert raw_listing in prompts[1]
    assert raw_listing not in prompts[2]
    assert "Your tools:" not in prompts[2]
    assert raw_listing not in prompts[3]
    assert ". list ok" in prompts[3]
    assert "Your tools:" in prompts[3]
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert raw_listing not in "\n".join(texts)
    assert "Fertig." in texts
    assert stored["memory"]["ownFiles"][0]["action"] == "list"


def test_orchestrator_stops_tool_rounds_and_calls_an_agent(monkeypatch, api_env) -> None:
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult
    from tests.run.test_validate import _orchestrator_doc

    executed = {"n": 0}

    def _execute(kind, *, config, args, secret=None):
        executed["n"] += 1
        return ExecuteResult(ok=True, result={"path": ".", "entries": ["x"]})

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" not in system:
            return CompletionResult(content="kurz", model=req.model, finish_reason="stop")
        if "Result from Schreiber" in blob or "characters:" in blob:
            return CompletionResult(
                content='{"action":"finish","text":"Fertig."}',
                model=req.model,
                finish_reason="stop",
            )
        if req.tools:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name="file_access", arguments='{"action":"list","path":"."}')
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(
            content='{"action":"call","agent":"Schreiber","task":"schreib"}',
            model=req.model,
            finish_reason="stop",
        )

    doc = _orchestrator_doc()
    doc["nodes"].append(
        {
            "id": "files",
            "type": "tool",
            "position": {"x": 0, "y": 0},
            "data": {"kind": "file_access", "rootPath": "C:/stories"},
        }
    )
    doc["edges"].append(
        {
            "id": "et",
            "source": "files",
            "sourceHandle": "tool",
            "target": "orch",
            "targetHandle": "tool",
        }
    )
    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 2
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Schreiber is done." in texts
    assert "Fertig." in texts


def test_num_ctx_wish_is_sent_to_ollama(monkeypatch, api_env) -> None:
    from tests.run.test_validate import _orchestrator_doc

    options: list[object] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        options.append(req.ollama_options)
        return CompletionResult(
            content='{"action":"finish","text":"Fertig."}',
            model=req.model,
            finish_reason="stop",
        )

    doc = _orchestrator_doc()
    for node in doc["nodes"]:
        if node["id"] == "llm":
            node["data"]["numCtx"] = 8192
    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "succeeded"
    assert options[0] == {"num_ctx": 8192}
    assert stored["memory"]["windows"][0]["contextMax"] == 8192
    assert stored["memory"]["raised"]["llama3.2:1b"] == 8192


def test_num_thread_is_sent_to_ollama(monkeypatch, api_env) -> None:
    from tests.run.test_validate import _orchestrator_doc

    options: list[object] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        options.append(req.ollama_options)
        return CompletionResult(
            content='{"action":"finish","text":"Fertig."}',
            model=req.model,
            finish_reason="stop",
        )

    doc = _orchestrator_doc()
    for node in doc["nodes"]:
        if node["id"] == "llm":
            node["data"]["numCtx"] = 8192
            node["data"]["numThread"] = 6
            node["data"]["numGpuLayers"] = 24
    monkeypatch.setattr("app.runtime.ollama.model_block_count", lambda *a, **k: 47)
    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "succeeded"
    assert options[0] == {"num_ctx": 8192, "num_thread": 6, "num_gpu": 25}


def test_num_gpu_percent_still_maps_for_old_graphs(monkeypatch, api_env) -> None:
    from tests.run.test_validate import _orchestrator_doc

    options: list[object] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        options.append(req.ollama_options)
        return CompletionResult(
            content='{"action":"finish","text":"Fertig."}',
            model=req.model,
            finish_reason="stop",
        )

    doc = _orchestrator_doc()
    for node in doc["nodes"]:
        if node["id"] == "llm":
            node["data"]["numGpuPercent"] = 50
    monkeypatch.setattr("app.runtime.ollama.model_block_count", lambda *a, **k: 47)
    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "succeeded"
    assert options[0] == {"num_gpu": 25}


def test_num_gpu_max_includes_output_slot(monkeypatch, api_env) -> None:
    from tests.run.test_validate import _orchestrator_doc

    options: list[object] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        options.append(req.ollama_options)
        return CompletionResult(
            content='{"action":"finish","text":"Fertig."}',
            model=req.model,
            finish_reason="stop",
        )

    doc = _orchestrator_doc()
    for node in doc["nodes"]:
        if node["id"] == "llm":
            node["data"]["numGpuLayers"] = 32
    monkeypatch.setattr("app.runtime.ollama.model_block_count", lambda *a, **k: 32)
    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "succeeded"
    assert options[0] == {"num_gpu": 33}


def test_llm_node_is_running_during_the_model_call(monkeypatch, api_env) -> None:
    from app.run.controller import get_controller
    from tests.run.test_validate import _orchestrator_doc

    seen: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        snap = get_controller().snapshot
        assert snap is not None
        for node in snap.graph.nodes:
            if node.type != "llm":
                continue
            runtime = snap.nodes_runtime.get(node.id)
            if runtime is not None and runtime.status == "running":
                seen.append(node.id)
                if runtime.llm is not None:
                    seen.append(runtime.llm.model)
        assert "llm" in snap.activity.current_node_ids
        return CompletionResult(
            content='{"action":"finish","text":"Fertig."}',
            model=req.model,
            finish_reason="stop",
        )

    stored = _drive(monkeypatch, _complete, doc=_orchestrator_doc())
    assert stored["outcome"] == "succeeded"
    assert "llm" in seen
    assert "llama3.2:1b" in seen
    from app.db.runs import list_steps

    steps = {row["node_id"]: row["status"] for row in list_steps(stored["id"])}
    assert steps.get("llm") == "idle"


def test_tool_and_knowledge_nodes_run_while_used(monkeypatch, api_env, tmp_path) -> None:
    from app.run.controller import get_controller
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult
    from tests.run.test_validate import _orchestrator_doc

    folder = tmp_path / "docs"
    folder.mkdir()
    monkeypatch.setattr("app.run.controller.index_node", lambda *a, **k: "ready")

    seen_tool: list[str] = []
    seen_kn: list[str] = []

    def _retrieve(*args, **kwargs):
        del args, kwargs
        snap = get_controller().snapshot
        assert snap is not None
        runtime = snap.nodes_runtime.get("kn")
        if runtime is not None and runtime.status == "running":
            seen_kn.append("kn")
        return []

    def _execute(kind, *, config, args, secret=None):
        del kind, config, args, secret
        snap = get_controller().snapshot
        assert snap is not None
        runtime = snap.nodes_runtime.get("files")
        if runtime is not None and runtime.status == "running":
            seen_tool.append("files")
        return ExecuteResult(ok=True, result={"path": ".", "entries": []})

    monkeypatch.setattr("app.run.harness.retrieve", _retrieve)
    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)
    agent_n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            if "characters:" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"schreib"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        if agent_n["n"] == 1:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name="file_access", arguments='{"action":"list","path":"."}')
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(content="kurz", model=req.model, finish_reason="stop")

    doc = _orchestrator_doc()
    doc["nodes"].extend(
        [
            {
                "id": "kn",
                "type": "knowledge",
                "position": {"x": 0, "y": 0},
                "data": {"sourcePath": str(folder), "embeddingModel": "nomic-embed-text"},
            },
            {
                "id": "files",
                "type": "tool",
                "position": {"x": 0, "y": 0},
                "data": {"kind": "file_access", "rootPath": "C:/stories"},
            },
        ]
    )
    doc["edges"].extend(
        [
            {
                "id": "ek",
                "source": "kn",
                "sourceHandle": "knowledge",
                "target": "ag",
                "targetHandle": "knowledge",
            },
            {
                "id": "et",
                "source": "files",
                "sourceHandle": "tool",
                "target": "ag",
                "targetHandle": "tool",
            },
        ]
    )
    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "succeeded"
    assert "kn" in seen_kn
    assert "files" in seen_tool
    from app.db.runs import list_steps

    steps = {row["node_id"]: row["status"] for row in list_steps(stored["id"])}
    assert steps.get("kn") == "idle"
    assert steps.get("files") == "idle"


def _tool_agent_doc() -> dict:
    from tests.run.test_validate import _orchestrator_doc

    doc = _orchestrator_doc()
    doc["nodes"].append(
        {
            "id": "files",
            "type": "tool",
            "position": {"x": 0, "y": 0},
            "data": {"kind": "file_access", "rootPath": "C:/stories"},
        }
    )
    doc["edges"].append(
        {
            "id": "et",
            "source": "files",
            "sourceHandle": "tool",
            "target": "ag",
            "targetHandle": "tool",
        }
    )
    return doc


def test_tool_agent_prose_is_nudged_then_calls(monkeypatch, api_env) -> None:
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult

    executed = {"n": 0}
    agent_n = {"n": 0}

    def _execute(kind, *, config, args, secret=None):
        del kind, config, args, secret
        executed["n"] += 1
        return ExecuteResult(ok=True, result={"path": "a.txt", "bytes": 3})

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            if "a.txt" in blob or "characters:" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"speichere"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        if agent_n["n"] == 1:
            assert "You must call a tool" in system
            return CompletionResult(content="Ich habe gespeichert.", model=req.model, finish_reason="stop")
        if agent_n["n"] == 2:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="file_access",
                        arguments='{"action":"write","path":"a.txt","content":"x"}',
                    )
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(content="ok", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 1
    assert agent_n["n"] == 3
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert any("Schreiber is done." in (item or "") or "Files:" in (item or "") for item in texts)


def test_tool_agent_without_a_call_is_an_anomaly(monkeypatch, api_env) -> None:
    agent_n = {"n": 0}
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            prompts.append(blob)
            if "no tool used" in blob or "Check with a tool" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"speichere"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        return CompletionResult(content="Ich habe gespeichert.", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert agent_n["n"] == 2
    assert any("no tool used" in item for item in prompts)
    texts = "\n".join(item["content"] or "" for item in (stored["chat"] or []))
    assert "Schreiber is done." not in texts
    assert "Fertig." in texts
    assert stored["memory"]["calls"][0]["error"] == "no tool used"


def test_mcp_answer_after_success_is_published(monkeypatch, api_env) -> None:
    from app.db import init
    from app.db.settings import put_mcp_server
    from app.mcp.models import McpToolInfo
    from app.runtime.models import ToolCall
    from tests.run.conftest import mini_doc

    init()
    put_mcp_server(
        "srv-9",
        {
            "name": "gh",
            "enabled": True,
            "cached_tools": [{"name": "search_repositories"}],
        },
    )
    raw = mini_doc()
    raw["nodes"].append(
        {
            "id": "mcp1",
            "type": "mcp",
            "position": {"x": 0, "y": 0},
            "data": {"mcpServerId": "srv-9"},
        }
    )
    raw["edges"].append(
        {
            "id": "em",
            "source": "mcp1",
            "sourceHandle": "tool",
            "target": "ag",
            "targetHandle": "tool",
        }
    )

    class FakeMcp:
        def open_for(self, ids, credential_overrides=None, root_overrides=None):
            return None

        def close_all(self):
            return None

        def is_enabled(self, sid):
            return sid == "srv-9"

        def root_path(self, sid):
            return None

        def listed_tools(self, sid):
            return [
                McpToolInfo(
                    name="search_repositories",
                    description="search",
                    input_schema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                )
            ]

        def call(self, server_id, tool_name, arguments):
            assert arguments.get("query") == "user:me"
            return {
                "ok": True,
                "result": {
                    "total_count": 1,
                    "items": [{"full_name": "me/repo", "html_url": "https://github.com/me/repo"}],
                },
            }

    fake = FakeMcp()
    monkeypatch.setattr("app.run.harness.get_mcp", lambda: fake)
    monkeypatch.setattr("app.run.controller.get_mcp", lambda: fake)
    n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        n["n"] += 1
        if n["n"] == 1:
            name = req.tools[0]["function"]["name"]
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name=name, arguments='{"query":"user:me"}')
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        assert "already have tool results" in system
        assert "me/repo" in blob
        return CompletionResult(content="Repo: me/repo", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=raw)
    assert stored["outcome"] == "succeeded"
    assert n["n"] == 2
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert any("Repo: me/repo" in (item or "") for item in texts)


def test_second_agent_keeps_only_its_ollama_model(monkeypatch, api_env) -> None:
    from app.runtime.models import OllamaModel
    from tests.run.conftest import keeps

    monkeypatch.setattr(
        "app.runtime.ollama.list_ollama_models",
        lambda *a, **k: [
            OllamaModel(name="writer", size_bytes=None),
            OllamaModel(name="saver", size_bytes=None),
            OllamaModel(name="llama3.2:1b", size_bytes=None),
        ],
    )

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        return CompletionResult(content="ok " + req.model, model=req.model, finish_reason="stop")

    doc = {
        "schemaVersion": 1,
        "name": "chain",
        "nodes": [
            {
                "id": "in",
                "type": "chat_input",
                "position": {"x": 0, "y": 0},
                "data": {"startMessage": "go", "requireInput": False},
            },
            {
                "id": "llm-w",
                "type": "llm",
                "position": {"x": 0, "y": 0},
                "data": {"provider": "ollama", "model": "writer"},
            },
            {
                "id": "llm-s",
                "type": "llm",
                "position": {"x": 0, "y": 0},
                "data": {"provider": "ollama", "model": "saver"},
            },
            {"id": "ag-w", "type": "agent", "position": {"x": 0, "y": 0}, "data": {"systemPrompt": "write"}},
            {"id": "ag-s", "type": "agent", "position": {"x": 0, "y": 0}, "data": {"systemPrompt": "save"}},
            {"id": "end", "type": "end", "position": {"x": 0, "y": 0}, "data": {}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "in",
                "sourceHandle": "message",
                "target": "ag-w",
                "targetHandle": "message",
            },
            {
                "id": "e2",
                "source": "llm-w",
                "sourceHandle": "llm",
                "target": "ag-w",
                "targetHandle": "llm",
            },
            {
                "id": "e3",
                "source": "ag-w",
                "sourceHandle": "handoff",
                "target": "ag-s",
                "targetHandle": "message",
            },
            {
                "id": "e4",
                "source": "llm-s",
                "sourceHandle": "llm",
                "target": "ag-s",
                "targetHandle": "llm",
            },
            {
                "id": "e5",
                "source": "ag-s",
                "sourceHandle": "message",
                "target": "end",
                "targetHandle": "message",
            },
        ],
    }
    stored = _drive(monkeypatch, _complete, doc=doc, user_texts=())
    assert stored["outcome"] == "succeeded"
    writer_keeps = [item for item in keeps if "writer" in item]
    saver_keeps = [item for item in keeps if "saver" in item]
    assert writer_keeps
    assert saver_keeps
    assert all("saver" not in item for item in writer_keeps)
    assert all("writer" not in item for item in saver_keeps)


def test_orchestrator_calls_a_role_alias(monkeypatch, api_env) -> None:
    from tests.run.test_validate import _orchestrator_doc

    doc = _orchestrator_doc()
    for node in doc["nodes"]:
        if node["id"] == "ag":
            node["data"]["displayName"] = "Senior"
    started = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            blob = "\n".join(message.content or "" for message in req.messages)
            if "Result from Senior" in blob or "characters:" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Senior-Coder","task":"scaffold"}',
                model=req.model,
                finish_reason="stop",
            )
        started["n"] += 1
        return CompletionResult(content="scaffold ok", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "succeeded"
    assert started["n"] == 1
    assert stored["memory"]["calls"][0]["name"] == "Senior"


def test_orchestrator_second_reply_must_call(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs

    orch_n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" not in system:
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        blob = "\n".join(message.content or "" for message in req.messages)
        orch_n["n"] += 1
        if "Result from Schreiber" in blob or "characters:" in blob:
            return CompletionResult(
                content='{"action":"finish","text":"Fertig."}',
                model=req.model,
                finish_reason="stop",
            )
        if orch_n["n"] == 1:
            return CompletionResult(
                content='{"action":"reply","text":"Ich starte Senior."}',
                model=req.model,
                finish_reason="stop",
            )
        if orch_n["n"] == 2:
            return CompletionResult(
                content='{"action":"reply","text":"Senior startet T1."}',
                model=req.model,
                finish_reason="stop",
            )
        return CompletionResult(
            content='{"action":"call","agent":"Schreiber","task":"schreib"}',
            model=req.model,
            finish_reason="stop",
        )

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Ich starte Senior." in texts
    assert "Senior startet T1." not in texts
    assert "Fertig." in texts
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert "run.orchestrator.action" in messages


def test_empty_tool_agent_result_is_an_anomaly(monkeypatch, api_env) -> None:
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult

    agent_n = {"n": 0}

    def _execute(kind, *, config, args, secret=None):
        del kind, config, args, secret
        return ExecuteResult(ok=True, result={"path": ".", "entries": []})

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            if "empty result" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"architektur"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        if agent_n["n"] == 1:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(id="c1", name="file_access", arguments='{"action":"list","path":"."}')
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(content="", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert stored["memory"]["calls"][0]["error"] == "empty result"
    texts = "\n".join(item["content"] or "" for item in (stored["chat"] or []))
    assert "Schreiber is done." not in texts
    assert "Fertig." in texts


def test_agent_keeps_going_after_many_successful_tools(monkeypatch, api_env) -> None:
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult

    executed = {"n": 0}
    agent_n = {"n": 0}

    def _execute(kind, *, config, args, secret=None):
        del kind, config, args, secret
        executed["n"] += 1
        return ExecuteResult(ok=True, result={"path": f"f{executed['n']}.txt", "bytes": 1})

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            if "f9.txt" in blob or "characters:" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"speichere"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        if agent_n["n"] <= 9:
            n = agent_n["n"]
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id=f"c{n}",
                        name="file_access",
                        arguments=f'{{"action":"write","path":"f{n}.txt","content":"x"}}',
                    )
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(content="ok", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 9
    assert stored["memory"]["calls"][0]["error"] == ""
    texts = "\n".join(item["content"] or "" for item in (stored["chat"] or []))
    assert "Fertig." in texts


def test_agent_stops_after_ten_failed_tools(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult

    executed = {"n": 0}
    agent_n = {"n": 0}
    prompts: list[str] = []

    def _execute(kind, *, config, args, secret=None):
        del kind, config, args, secret
        executed["n"] += 1
        return ExecuteResult(ok=False, result="denied")

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            prompts.append(blob)
            if "too many tool failures" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"speichere"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        assert agent_n["n"] == 1
        return CompletionResult(
            content=None,
            tool_calls=[
                ToolCall(
                    id=f"c{i}",
                    name="file_access",
                    arguments=f'{{"action":"write","path":"f{i}.txt","content":"x"}}',
                )
                for i in range(10)
            ],
            model=req.model,
            finish_reason="tool_calls",
        )

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 10
    assert agent_n["n"] == 1
    assert stored["memory"]["calls"][0]["error"] == "too many tool failures"
    assert any("too many tool failures" in item for item in prompts)
    texts = "\n".join(item["content"] or "" for item in (stored["chat"] or []))
    assert "Schreiber is done." not in texts
    assert "Fertig." in texts
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert "run.agent.toolFailures" in messages


def test_tool_agent_think_then_calls(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult

    executed = {"n": 0}
    agent_n = {"n": 0}

    def _execute(kind, *, config, args, secret=None):
        del kind, config, args, secret
        executed["n"] += 1
        return ExecuteResult(ok=True, result={"path": "a.txt", "bytes": 3})

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            if "a.txt" in blob or "characters:" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"speichere"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        if agent_n["n"] == 1:
            assert "You may think first" in system
            assert "You must call a tool" in system
            return CompletionResult(
                content='{"action":"think","text":"plan the write"}',
                model=req.model,
                finish_reason="stop",
            )
        if agent_n["n"] == 2:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="file_access",
                        arguments='{"action":"write","path":"a.txt","content":"x"}',
                    )
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(content="ok", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 1
    assert agent_n["n"] == 3
    assert stored["memory"]["calls"][0]["error"] == ""
    texts = "\n".join(item["content"] or "" for item in (stored["chat"] or []))
    assert "plan the write" not in texts
    assert "Fertig." in texts
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert "run.agent.think" in messages
    assert "run.agent.thinkLimit" not in messages


def test_agent_two_thinks_then_calls(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult

    executed = {"n": 0}
    agent_n = {"n": 0}
    trailing: list[int] = []

    def _trailing_assistants(messages) -> int:
        n = 0
        for message in reversed(messages):
            if message.role == "assistant":
                n += 1
                continue
            break
        return n

    def _execute(kind, *, config, args, secret=None):
        del kind, config, args, secret
        executed["n"] += 1
        return ExecuteResult(ok=True, result={"path": "a.txt", "bytes": 3})

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            if "a.txt" in blob or "characters:" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"speichere"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        if agent_n["n"] == 1:
            return CompletionResult(
                content='{"action":"think","text":"first plan"}',
                model=req.model,
                finish_reason="stop",
            )
        if agent_n["n"] == 2:
            assert _trailing_assistants(req.messages) == 1
            return CompletionResult(
                content='{"action":"think","text":"second plan"}',
                model=req.model,
                finish_reason="stop",
            )
        if agent_n["n"] == 3:
            n = _trailing_assistants(req.messages)
            trailing.append(n)
            assert n == 1
            think_msgs = [m.content for m in req.messages if m.role == "assistant"]
            assert think_msgs[-1] == '{"action":"think","text":"second plan"}'
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="file_access",
                        arguments='{"action":"write","path":"a.txt","content":"x"}',
                    )
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(content="ok", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 1
    assert agent_n["n"] == 4
    assert trailing == [1]
    texts = "\n".join(item["content"] or "" for item in (stored["chat"] or []))
    assert "first plan" not in texts
    assert "second plan" not in texts
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert messages.count("run.agent.think") == 2


def test_agent_think_from_reasoning_then_calls(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult

    executed = {"n": 0}
    agent_n = {"n": 0}

    def _execute(kind, *, config, args, secret=None):
        del kind, config, args, secret
        executed["n"] += 1
        return ExecuteResult(ok=True, result={"path": "a.txt", "bytes": 3})

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            if "a.txt" in blob or "characters:" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"speichere"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        if agent_n["n"] == 1:
            return CompletionResult(
                content=None,
                reasoning="plan the write",
                model=req.model,
                finish_reason="stop",
            )
        if agent_n["n"] == 2:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="file_access",
                        arguments='{"action":"write","path":"a.txt","content":"x"}',
                    )
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(content="ok", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 1
    assert agent_n["n"] == 3
    texts = "\n".join(item["content"] or "" for item in (stored["chat"] or []))
    assert "plan the write" not in texts
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert "run.agent.think" in messages


def test_agent_think_limit_is_an_anomaly(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs

    monkeypatch.setattr("app.run.harness.MAX_AGENT_THINKS", 2)
    agent_n = {"n": 0}
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            prompts.append(blob)
            if "too many thinks" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"speichere"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        return CompletionResult(
            content='{"action":"think","text":"still planning"}',
            model=req.model,
            finish_reason="stop",
        )

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert agent_n["n"] == 2
    assert stored["memory"]["calls"][0]["error"] == "too many thinks"
    assert any("too many thinks" in item for item in prompts)
    texts = "\n".join(item["content"] or "" for item in (stored["chat"] or []))
    assert "still planning" not in texts
    assert "Fertig." in texts
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert "run.agent.think" in messages
    assert "run.agent.thinkLimit" in messages


def test_agent_one_token_think_loop_stops_after_five(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs

    agent_n = {"n": 0}
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            prompts.append(blob)
            if "think loop" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"speichere"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        return CompletionResult(
            content='{"action":"think","text":"."}',
            usage=CompletionUsage(prompt_tokens=32, completion_tokens=1),
            model=req.model,
            finish_reason="stop",
        )

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert agent_n["n"] == 5
    assert stored["memory"]["calls"][0]["error"] == "think loop"
    assert any("think loop" in item for item in prompts)
    texts = "\n".join(item["content"] or "" for item in (stored["chat"] or []))
    assert "Fertig." in texts
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert messages.count("run.agent.think") == 5
    assert "run.agent.thinkLoop" in messages
    assert "run.agent.thinkLimit" not in messages


def _linear_file_doc() -> dict:
    doc = mini_doc(startMessage="go")
    doc["nodes"].append(
        {
            "id": "files",
            "type": "tool",
            "position": {"x": 0, "y": 0},
            "data": {"kind": "file_access", "rootPath": "C:/stories"},
        }
    )
    doc["edges"].append(
        {
            "id": "et",
            "source": "files",
            "sourceHandle": "tool",
            "target": "ag",
            "targetHandle": "tool",
        }
    )
    return doc


def test_linear_write_then_short_think_succeeds(monkeypatch, api_env) -> None:
    from app.db.runs import list_logs, list_steps
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult

    executed = {"n": 0}

    def _execute(kind, *, config, args, secret=None):
        del kind, config, secret
        executed["n"] += 1
        return ExecuteResult(ok=True, result={"path": args.get("path") or "tiger.txt", "bytes": 20})

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        if not any(m.role == "tool" for m in req.messages):
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="file_access",
                        arguments='{"action":"write","path":"tiger.txt","content":"hi"}',
                    )
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(
            content=None,
            reasoning="Fertig.",
            usage=CompletionUsage(prompt_tokens=32, completion_tokens=5),
            model=req.model,
            finish_reason="stop",
        )

    stored = _drive(monkeypatch, _complete, doc=_linear_file_doc(), user_texts=())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 1
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert "Fertig." in texts
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert "run.agent.done" in messages
    assert "run.agent.thinkLoop" not in messages
    assert "run.failed" not in messages
    steps = {row["node_id"]: row["status"] for row in list_steps(stored["id"])}
    assert steps.get("ag") == "done"
    assert steps.get("end") == "done"


def test_write_then_long_think_then_second_write(monkeypatch, api_env) -> None:
    from app.runtime.models import ToolCall
    from app.tools.models import ExecuteResult

    executed = {"n": 0}
    agent_n = {"n": 0}

    def _execute(kind, *, config, args, secret=None):
        del kind, config, secret
        executed["n"] += 1
        return ExecuteResult(ok=True, result={"path": args.get("path") or "a.txt", "bytes": 3})

    monkeypatch.setattr("app.run.harness.tools_execute.execute_first_party", _execute)

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        blob = "\n".join(message.content or "" for message in req.messages)
        if "You orchestrate" in system:
            if "b.txt" in blob or "characters:" in blob:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"speichere"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        if agent_n["n"] == 1:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="file_access",
                        arguments='{"action":"write","path":"a.txt","content":"one"}',
                    )
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        if agent_n["n"] == 2:
            return CompletionResult(
                content='{"action":"think","text":"next I write the second file with the rest of the story"}',
                usage=CompletionUsage(prompt_tokens=40, completion_tokens=80),
                model=req.model,
                finish_reason="stop",
            )
        if agent_n["n"] == 3:
            return CompletionResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="2",
                        name="file_access",
                        arguments='{"action":"write","path":"b.txt","content":"two"}',
                    )
                ],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(content="ok", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert executed["n"] == 2
    assert agent_n["n"] >= 3
    texts = "\n".join(item["content"] or "" for item in (stored["chat"] or []))
    assert "Fertig." in texts


def test_agent_think_keeps_llm_busy(monkeypatch, api_env) -> None:
    from app.run import harness as harness_mod

    flags: list[bool] = []
    real = harness_mod._set_llm

    def _wrap(ctrl, compiled, llm_node_id, *, busy: bool) -> None:
        flags.append(busy)
        real(ctrl, compiled, llm_node_id, busy=busy)

    monkeypatch.setattr("app.run.harness._set_llm", _wrap)
    agent_n = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" in system:
            if agent_n["n"]:
                return CompletionResult(
                    content='{"action":"finish","text":"Fertig."}',
                    model=req.model,
                    finish_reason="stop",
                )
            return CompletionResult(
                content='{"action":"call","agent":"Schreiber","task":"schreib"}',
                model=req.model,
                finish_reason="stop",
            )
        agent_n["n"] += 1
        if agent_n["n"] < 3:
            return CompletionResult(
                content='{"action":"think","text":"planning"}',
                model=req.model,
                finish_reason="stop",
            )
        return CompletionResult(content="ok", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_tool_agent_doc())
    assert stored["outcome"] == "succeeded"
    assert agent_n["n"] >= 3
    longest = 0
    streak = 0
    for flag in flags:
        if flag:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 0
    assert longest >= 3
