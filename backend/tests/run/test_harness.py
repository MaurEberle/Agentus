from __future__ import annotations

from app.runtime.models import CompletionRequest, CompletionResult
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


def test_three_prose_calls_fail_without_asking(monkeypatch, api_env) -> None:
    prose = 'Call agent-7fef4344 with the full German story under the title "Der Tiger auf dem Bauernhof".'
    prompts: list[str] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        prompts.append("\n".join(message.content or "" for message in req.messages))
        return CompletionResult(content=prose, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.orchestrator.unreadable"
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert prose not in "\n".join(texts)
    assert all(prose not in item for item in prompts)
    rejected = (stored["memory"] or {}).get("rejected") or []
    assert len(rejected) == 3
    assert all(item["reason"] == "unreadable" for item in rejected)


def test_orchestrator_prompt_does_not_contain_the_manuscript(monkeypatch, api_env) -> None:
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
    assert manuscript not in prompts[1]
    assert "Previous agent result" not in prompts[1]
    assert f"characters: {len(manuscript)}" in prompts[1]
    assert stored["memory"]["calls"][0]["text"] == manuscript
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert manuscript not in "\n".join(texts)
    assert "Schreiber is done." in texts
    done = next(item for item in stored["chat"] if item["content"] == "Schreiber is done.")
    assert done["messageKey"] == "monitoring.chat.agentDone"
    assert done["messageParams"]["name"] == "Schreiber"


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
