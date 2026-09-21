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
