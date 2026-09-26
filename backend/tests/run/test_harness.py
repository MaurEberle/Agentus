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
    from app.db.runs import list_logs

    waits = [row for row in list_logs(started["runId"]) if row["message"] == "run.wait.human"]
    assert len(waits) == 2


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
        if "characters:" in blob:
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
