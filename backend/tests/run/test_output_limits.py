"""R1: automatic output cap per call, wall-clock limit, and cut-off reasoning handling."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

from app.db.runs import list_logs
from app.run.turn_runtime import _output_cap
from app.run.window import WindowChoice
from app.runtime.models import ChatMessage, CompletionRequest, CompletionResult, ToolCall
from tests.run.test_harness import _drive, _linear_file_doc


def _llm(provider="ollama", num_ctx=None, max_tokens=None):
    return SimpleNamespace(provider=provider, num_ctx=num_ctx, max_tokens=max_tokens)


def _window(ctx):
    return WindowChoice(num_ctx=ctx, context_max=ctx, fits=True)


# ---------------------------------------------------------------- cap rules
def test_cap_follows_the_users_context() -> None:
    # The Junior run: 131k window, 8k prompt -> 16k instead of 123k.
    assert _output_cap(_llm(num_ctx=131072), _window(131072), 7970) == (16384, True)
    assert _output_cap(_llm(num_ctx=32768), _window(32768), 2000) == (8192, True)
    assert _output_cap(_llm(num_ctx=8192), _window(8192), 1000) == (4096, True)


def test_cap_never_exceeds_the_room_the_prompt_leaves() -> None:
    cap, auto = _output_cap(_llm(num_ctx=8192), _window(8192), 7000)
    assert auto and cap == 1192
    # Even a full prompt keeps a minimal answer room; the window itself is not raised.
    assert _output_cap(_llm(num_ctx=8192), _window(8192), 9000) == (1024, True)


def test_node_max_tokens_wins_and_cloud_is_untouched() -> None:
    assert _output_cap(_llm(max_tokens=2048, num_ctx=131072), _window(131072), 100) == (2048, False)
    assert _output_cap(_llm(provider="openai"), _window(None), 100) == (None, False)
    assert _output_cap(_llm(), WindowChoice(num_ctx=None, context_max=None, fits=True), 100) == (16384, True)


def test_window_choice_does_not_see_the_auto_cap(monkeypatch, api_env) -> None:
    """The automatic cap must not make the window logic grow the user's num_ctx."""
    seen: list[object] = []
    from app.run import window as run_window

    real_need = run_window.prompt_need

    def _need(messages, max_tokens, *, thinking=False):
        seen.append(max_tokens)
        return real_need(messages, max_tokens, thinking=thinking)

    monkeypatch.setattr("app.run.window.prompt_need", _need)
    caps: list[int | None] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        caps.append(req.max_tokens)
        return CompletionResult(content="Fertig.", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_linear_file_doc(), user_texts=())
    assert stored["outcome"] == "succeeded"
    assert seen and all(value is None for value in seen)
    assert caps and all(isinstance(cap, int) and cap > 0 for cap in caps)
    start = next(row for row in list_logs(stored["id"]) if row["message"] == "run.llm.start")
    assert (start.get("payload") or {}).get("maxTokensAuto") is True


# ---------------------------------------------------------------- wall clock
class _EndlessSse(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        chunk = {"choices": [{"delta": {"content": "x"}, "index": 0}]}
        try:
            while True:
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.flush()
                time.sleep(0.1)
        except OSError:
            return

    def log_message(self, *args) -> None:
        return


def test_call_is_stopped_after_its_wall_clock_limit() -> None:
    """Tokens keep coming (idle watchdog never fires), the total limit still ends the call."""
    from app.runtime.completions import _stream_once

    server = ThreadingHTTPServer(("127.0.0.1", 0), _EndlessSse)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
        req = CompletionRequest(
            provider="openai_compat",
            model="m",
            messages=[ChatMessage(role="user", content="hi")],
            timeout_sec=30,
            max_duration_sec=1.0,
        )
        started = time.monotonic()
        events = list(_stream_once(url, {}, {"model": "m", "stream": True}, req))
        elapsed = time.monotonic() - started
    finally:
        server.shutdown()
    errors = [event for event in events if event.kind == "error"]
    assert errors and errors[0].error_key == "runtime.generationLimit"
    assert any(event.kind == "delta" for event in events)
    assert elapsed < 5


# ---------------------------------------------------------------- reactions
def test_agent_overrun_becomes_an_anomaly(monkeypatch, api_env) -> None:
    from app.runtime.errors import RuntimeApiError

    prompts: list[str] = []
    agent_calls = {"n": 0}

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" not in system:
            agent_calls["n"] += 1
            raise RuntimeApiError("runtime.generationLimit", detail="stopped after 20 min")
        prompts.append("\n".join(m.content or "" for m in req.messages))
        if len(prompts) == 1:
            content = '{"action":"call","agent":"Schreiber","task":"schreib"}'
        else:
            content = '{"action":"finish","text":"Abgebrochen."}'
        return CompletionResult(content=content, model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    # No same-prompt retry and no continuation for an overrun.
    assert agent_calls["n"] == 1
    assert "runtime.generationLimit" in prompts[1] and "Anomaly for" in prompts[1]


def test_orchestrator_overrun_gets_one_brief_retry(monkeypatch, api_env) -> None:
    from app.runtime.errors import RuntimeApiError

    orch = {"n": 0}
    notes: list[bool] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        system = req.messages[0].content or ""
        if "You orchestrate" not in system:
            return CompletionResult(content="agent-text", model=req.model, finish_reason="stop")
        orch["n"] += 1
        notes.append(any("took too long" in (m.content or "") for m in req.messages))
        if orch["n"] == 1:
            raise RuntimeApiError("runtime.generationLimit")
        return CompletionResult(content='{"action":"finish","text":"Fertig."}', model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete)
    assert stored["outcome"] == "succeeded"
    assert notes == [False, True]


def test_cut_off_reasoning_is_clipped_and_followed_by_a_nudge(monkeypatch, api_env) -> None:
    from app.tools.models import ExecuteResult

    monkeypatch.setattr(
        "app.run.turn_runtime.tools_execute.execute_first_party",
        lambda kind, *, config, args, secret=None: ExecuteResult(ok=True, result={"path": "a.txt", "bytes": 1}),
    )
    seen: list[list[ChatMessage]] = []

    def _complete(req: CompletionRequest, should_abort=None, on_progress=None) -> CompletionResult:
        seen.append(list(req.messages))
        if len(seen) == 1:
            return CompletionResult(content="", reasoning="denke " * 5000, model=req.model, finish_reason="length")
        if not any(m.role == "tool" for m in req.messages):
            return CompletionResult(
                content=None,
                tool_calls=[ToolCall(id="w", name="file_access", arguments='{"action":"write","path":"a.txt","content":"x"}')],
                model=req.model,
                finish_reason="tool_calls",
            )
        return CompletionResult(content="Fertig.", model=req.model, finish_reason="stop")

    stored = _drive(monkeypatch, _complete, doc=_linear_file_doc(), user_texts=())
    assert stored["outcome"] == "succeeded"
    second = seen[1]
    assert any("hit the output limit" in (m.content or "") for m in second)
    longest_assistant = max(len(m.content or "") for m in second if m.role == "assistant")
    assert longest_assistant < 2_200
