"""Linear chain: one payload per edge (Paket 6 / H8), honest failure (H7), roots only (M9), no Ollama needed (H3)."""

from __future__ import annotations

from app.db.runs import list_logs
from app.runtime.models import CompletionRequest, CompletionResult
from tests.run.conftest import keeps
from tests.run.test_harness import _drive


def _node(node_id: str, kind: str, data: dict | None = None) -> dict:
    return {"id": node_id, "type": kind, "position": {"x": 0, "y": 0}, "data": data or {}}


def _edge(edge_id: str, source: str, source_handle: str, target: str, target_handle: str) -> dict:
    return {
        "id": edge_id,
        "source": source,
        "sourceHandle": source_handle,
        "target": target,
        "targetHandle": target_handle,
    }


def _chain(*, chat: bool = True, provider: str = "ollama") -> dict:
    llm = {"provider": provider, "model": "llama3.2:1b"}
    if provider != "ollama":
        llm = {"provider": provider, "model": "cloud-model", "credentialId": "cred-1"}
    nodes = [
        _node("llm1", "llm", dict(llm)),
        _node("llm2", "llm", dict(llm)),
        _node("a", "agent", {"systemPrompt": "SYS-A", "displayName": "Erster"}),
        _node("b", "agent", {"systemPrompt": "SYS-B", "displayName": "Zweiter"}),
        _node("end", "end"),
    ]
    edges = [
        _edge("1", "llm1", "llm", "a", "llm"),
        _edge("2", "llm2", "llm", "b", "llm"),
        _edge("3", "a", "message", "b", "message"),
        _edge("4", "b", "message", "end", "message"),
    ]
    if chat:
        nodes.insert(0, _node("in", "chat_input"))
        edges.insert(0, _edge("0", "in", "message", "a", "message"))
    return {"schemaVersion": 1, "name": "chain", "nodes": nodes, "edges": edges}


def _recorder(calls: list[tuple[str, list[tuple[str, str]]]]):
    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        who = "A" if system.startswith("SYS-A") else "B"
        calls.append((who, [(m.role, m.content or "") for m in req.messages[1:]]))
        return CompletionResult(content=f"OUT-{who}", model=req.model, finish_reason="stop")

    return _complete


def test_second_agent_gets_the_first_answer_as_its_one_user_message(monkeypatch, api_env) -> None:
    calls: list[tuple[str, list[tuple[str, str]]]] = []
    stored = _drive(monkeypatch, _recorder(calls), doc=_chain(), user_texts=("Bitte uebersetze: Hallo",))
    assert stored["outcome"] == "succeeded"
    assert calls == [
        ("A", [("user", "Bitte uebersetze: Hallo")]),
        # Not the user line again, not an assistant turn: the text of the incoming edge.
        ("B", [("user", "OUT-A")]),
    ]
    # Both answers still reach the run chat (the driver queues the user line directly).
    texts = [item["content"] for item in (stored["chat"] or [])]
    assert texts == ["OUT-A", "OUT-B"]


def test_chain_without_chat_runs_each_agent_once_and_hands_on(monkeypatch, api_env) -> None:
    calls: list[tuple[str, list[tuple[str, str]]]] = []
    stored = _drive(monkeypatch, _recorder(calls), doc=_chain(chat=False), user_texts=())
    assert stored["outcome"] == "succeeded"
    assert calls == [
        ("A", [("user", "Begin.")]),
        ("B", [("user", "OUT-A")]),
    ]


def test_linear_run_fails_when_the_answer_is_cut_off_twice(monkeypatch, api_env) -> None:
    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        return CompletionResult(content="partial", model=req.model, finish_reason="length")

    stored = _drive(monkeypatch, _complete, doc=_chain(), user_texts=("Hi",))
    # H7: this used to end as succeeded with an empty chat.
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.agent.outputLimit"
    assert stored["error_node_id"] == "a"
    messages = [row["message"] for row in list_logs(stored["id"])]
    assert "run.agent.outputLimit" in messages
    assert "run.succeeded" not in messages


def test_linear_run_fails_when_the_prompt_does_not_fit(monkeypatch, api_env) -> None:
    from app.run.window import WindowChoice

    monkeypatch.setattr(
        "app.run.turn_runtime._bind_window",
        lambda *a, **k: WindowChoice(num_ctx=None, context_max=8192, fits=False),
    )
    calls: list[tuple[str, list[tuple[str, str]]]] = []
    stored = _drive(monkeypatch, _recorder(calls), doc=_chain(), user_texts=("Hi",))
    assert calls == []
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.agent.window"


def test_cloud_only_network_starts_without_ollama(monkeypatch, api_env) -> None:
    from app.db.vault import put as vault_put
    from app.runtime.errors import RuntimeApiError

    def _down(*args, **kwargs):
        raise RuntimeApiError("runtime.unreachable")

    monkeypatch.setattr("app.runtime.ollama.list_ollama_models", _down)
    vault_put("cred-1", "sk-test-0000000000")
    calls: list[tuple[str, list[tuple[str, str]]]] = []
    stored = _drive(
        monkeypatch, _recorder(calls), doc=_chain(provider="openai"), user_texts=("Hi",)
    )
    # H3: the start used to fail with 409 runtime.unreachable.
    assert stored["outcome"] == "succeeded"
    assert [who for who, _ in calls] == ["A", "B"]
    # Nothing was unloaded or kept on a daemon this network does not use.
    assert keeps == []


def test_missing_prompt_usage_is_stored_as_the_estimate(monkeypatch, api_env) -> None:
    """N3: without prompt usage the history showed 0 input tokens."""
    from app.db.runs import list_calls
    from app.runtime.models import CompletionUsage
    from tests.run.conftest import mini_doc

    def _complete(req, should_abort=None, on_progress=None):
        return CompletionResult(
            content="Antwort",
            model=req.model,
            finish_reason="stop",
            usage=CompletionUsage(completion_tokens=3),
        )

    stored = _drive(monkeypatch, _complete, doc=mini_doc())
    calls = list_calls(stored["id"])
    assert calls
    assert all((row["tokens_in"] or 0) > 0 for row in calls)
    assert calls[0]["tokens_out"] == 3


def test_chain_without_reaching_an_end_says_why(monkeypatch, api_env) -> None:
    """N13: the run failed at the end without any message."""
    from app.run import validate as run_validate
    from tests.run.conftest import mini_doc

    # Validation would refuse this graph; the runtime still needs its own message.
    monkeypatch.setattr(run_validate, "_chain_reaches_end", lambda *a, **k: True)
    doc = mini_doc()
    doc["edges"] = [edge for edge in doc["edges"] if edge["id"] != "e3"]

    def _complete(req, should_abort=None, on_progress=None):
        return CompletionResult(content="Antwort", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=doc)
    assert stored["outcome"] == "failed"
    assert stored["error_message"] == "run.noEnd"
    assert "run.noEnd" in [row["message"] for row in list_logs(stored["id"])]


def test_live_updates_leave_graph_and_chat_out(monkeypatch, api_env) -> None:
    """N12: every token and node update carried the whole snapshot, chat included."""
    from app.run import turn_runtime
    from app.runtime.models import CompletionUsage
    from tests.run.conftest import mini_doc

    sent: list[dict] = []
    real = turn_runtime.publish

    def _capture(event, data):
        if event == "run":
            sent.append(data)
        return real(event, data)

    monkeypatch.setattr(turn_runtime, "publish", _capture)

    def _complete(req, should_abort=None, on_progress=None):
        return CompletionResult(
            content="Antwort", model=req.model, finish_reason="stop", usage=CompletionUsage(prompt_tokens=5, completion_tokens=2)
        )

    stored = _drive(monkeypatch, _complete, doc=mini_doc())
    assert stored["outcome"] == "succeeded"
    assert sent
    assert all(set(item) == {"runId", "nodesRuntime", "activity"} for item in sent)
    assert any(item["nodesRuntime"].get("ag", {}).get("status") == "running" for item in sent)
