from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.runtime.completions import (
    _ollama_messages,
    _openai_messages,
    _parse_usage,
    complete,
    complete_live,
    complete_stream,
    estimate_token_count,
)
from app.runtime.errors import RuntimeApiError
from app.runtime.models import ChatMessage, CompletionRequest, ToolCall
from tests.runtime.transport import install_transport

_MSG = [ChatMessage(role="user", content="hi")]


@pytest.fixture(autouse=True)
def _stub_block_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.runtime.completions.model_block_count", lambda *a, **k: 16)


def _chat_ok(content: str = "hello", tool_calls: object | None = None) -> dict:
    message: dict = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "model": "llama3.2:1b",
        "choices": [{"message": message, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
    }


def test_complete_content(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_chat_ok())

    install_transport(monkeypatch, handler)
    result = complete(
        CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
    )
    assert result.content == "hello"
    assert result.tool_calls == []
    assert result.usage is not None
    assert result.usage.prompt_tokens == 1


def test_complete_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_chat_ok(
                content=None,
                tool_calls=[
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "http", "arguments": "{\"url\":\"x\"}"},
                    }
                ],
            ),
        )

    install_transport(monkeypatch, handler)
    result = complete(
        CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
    )
    assert result.tool_calls[0].name == "http"
    assert result.tool_calls[0].arguments == '{"url":"x"}'


def test_complete_401(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "no"})

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as err:
        complete(
            CompletionRequest(
                provider="xai",
                model="grok",
                messages=_MSG,
                secret="sk-test-secret",
            )
        )
    assert err.value.error_key == "runtime.unauthorized"


def test_complete_ollama_no_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers)
        return httpx.Response(200, json=_chat_ok())

    install_transport(monkeypatch, handler)
    complete(
        CompletionRequest(
            provider="ollama",
            model="llama3.2:1b",
            messages=_MSG,
            secret="should-not-send",
            credential_id="cred-1",
        )
    )
    assert "authorization" not in {k.lower() for k in seen[0].keys()}


def test_complete_xai_missing_secret_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call HTTP")

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as err:
        complete(CompletionRequest(provider="xai", model="grok", messages=_MSG))
    assert err.value.error_key == "runtime.missingCredential"


def test_stream_two_deltas_then_done(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["stream"] is True
        assert "stream_options" not in body
        assert body["options"]["num_gpu"] == 16
        return httpx.Response(200, content=payload)

    install_transport(monkeypatch, handler)
    events = list(
        complete_stream(
            CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
        )
    )
    texts = [e.text for e in events if e.kind == "delta"]
    assert texts == ["Hel", "lo"]
    assert events[-1].kind == "done"


def test_secret_not_in_logs(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_chat_ok())

    install_transport(monkeypatch, handler)
    secret = "sk-super-secret-xyz"
    with caplog.at_level(logging.DEBUG):
        complete(
            CompletionRequest(
                provider="xai",
                model="grok",
                messages=_MSG,
                secret=secret,
            )
        )
    assert secret not in caplog.text
    dumped = CompletionRequest(
        provider="xai", model="grok", messages=_MSG, secret=secret
    ).model_dump()
    assert secret not in str(dumped)
    assert "secret" not in dumped


def test_complete_read_timeout_is_runtime_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as err:
        complete(
            CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
        )
    assert err.value.error_key == "runtime.timeout"


def test_complete_connect_error_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as err:
        complete(
            CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
        )
    assert err.value.error_key == "runtime.unreachable"


def test_stream_read_timeout_error_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    install_transport(monkeypatch, handler)
    events = list(
        complete_stream(
            CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
        )
    )
    assert events[-1].kind == "error"
    assert events[-1].error_key == "runtime.timeout"


def test_complete_live_aggregates_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["stream"] is True
        assert "stream_options" not in body
        return httpx.Response(200, content=payload)

    install_transport(monkeypatch, handler)
    result = complete_live(
        CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
    )
    assert result.content == "Hello"
    assert result.finish_reason == "stop"


def test_estimate_token_count() -> None:
    assert estimate_token_count("") == 0
    assert estimate_token_count("abcd") == 1
    assert estimate_token_count("abcdefgh") == 2


def test_complete_live_reports_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        b'data: {"choices":[{"delta":{"content":"Hello world"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"!"}}]}\n\n'
        b'data: {"usage":{"prompt_tokens":3,"completion_tokens":4}}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    install_transport(monkeypatch, handler)
    seen: list[tuple[int, float]] = []
    result = complete_live(
        CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG),
        on_progress=lambda count, rate: seen.append((count, rate)),
    )
    assert result.content == "Hello world!"
    assert result.usage is not None
    assert result.usage.completion_tokens == 4
    assert seen
    assert seen[-1][0] == 4
    assert seen[-1][1] > 0


def test_parse_usage_field_aliases() -> None:
    openai = _parse_usage({"prompt_tokens": 3, "completion_tokens": 7})
    assert openai is not None
    assert openai.prompt_tokens == 3
    assert openai.completion_tokens == 7
    ollama = _parse_usage({"prompt_eval_count": 11, "eval_count": 22})
    assert ollama is not None
    assert ollama.prompt_tokens == 11
    assert ollama.completion_tokens == 22
    partial = _parse_usage({"completion_tokens": 9})
    assert partial is not None
    assert partial.prompt_tokens == 0
    assert partial.completion_tokens == 9
    compat = _parse_usage({"input_tokens": 4, "output_tokens": 8})
    assert compat is not None
    assert compat.prompt_tokens == 4
    assert compat.completion_tokens == 8
    assert _parse_usage({}) is None
    assert _parse_usage({"prompt_tokens": 0, "completion_tokens": 0}) is not None


def test_stream_include_usage_empty_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        b'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
        b'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":12}}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    install_transport(monkeypatch, handler)
    result = complete_live(
        CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
    )
    assert result.content == "Hi"
    assert result.usage is not None
    assert result.usage.completion_tokens == 12
    assert result.usage.prompt_tokens == 5


def test_stream_zero_usage_falls_back_to_estimate(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        b'data: {"choices":[{"delta":{"content":"abcdefgh"}}]}\n\n'
        b'data: {"choices":[],"usage":{"prompt_tokens":0,"completion_tokens":0}}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    install_transport(monkeypatch, handler)
    result = complete_live(
        CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
    )
    assert result.usage is not None
    assert result.usage.completion_tokens == estimate_token_count("abcdefgh")


def test_small_deltas_match_the_full_text_estimate(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"".join(
        f'data: {{"choices":[{{"delta":{{"content":"{ch}"}}}}]}}\n\n'.encode() for ch in "abcdefgh"
    ) + b"data: [DONE]\n\n"
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    install_transport(monkeypatch, handler)
    result = complete_live(
        CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG),
        on_progress=lambda count, rate: seen.append(count),
    )
    expect = estimate_token_count("abcdefgh")
    assert result.usage is not None
    assert result.usage.completion_tokens == expect
    assert seen[-1] == expect


def test_thinking_delta_counts_tokens_not_content(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        b'data: {"choices":[{"delta":{"reasoning":"abcdefgh"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    install_transport(monkeypatch, handler)
    result = complete_live(
        CompletionRequest(provider="ollama", model="qwen3", messages=_MSG),
        on_progress=lambda count, rate: seen.append(count),
    )
    assert result.content == "ok"
    assert result.usage is not None
    assert result.usage.completion_tokens >= estimate_token_count("abcdefgh")
    assert seen


def test_complete_live_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'data: {"choices":[{"delta":{"content":"x"}}]}\n\n' b"data: [DONE]\n\n",
        )

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as err:
        complete_live(
            CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG),
            should_abort=lambda: True,
        )
    assert err.value.error_key == "run.cancelled"


def test_openai_stream_sends_stream_options(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["stream_options"] == {"include_usage": True}
        return httpx.Response(200, content=b"data: [DONE]\n\n")

    install_transport(monkeypatch, handler)
    events = list(
        complete_stream(
            CompletionRequest(
                provider="xai",
                model="grok",
                messages=_MSG,
                secret="sk-test-secret",
            )
        )
    )
    assert events[-1].kind == "done"


def test_complete_native_ollama_body(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "llama3.2:1b",
                "message": {"role": "assistant", "content": "hi native"},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 4,
                "eval_count": 2,
            },
        )

    install_transport(monkeypatch, handler)
    result = complete(
        CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
    )
    assert result.content == "hi native"
    assert result.finish_reason == "stop"
    assert result.usage is not None
    assert result.usage.prompt_tokens == 4
    assert result.usage.completion_tokens == 2


def test_native_stream_deltas(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = (
        b'{"message":{"role":"assistant","content":"Hel"},"done":false}\n'
        b'{"message":{"role":"assistant","content":"lo"},"done":false}\n'
        b'{"message":{"role":"assistant","content":""},"done":true,"done_reason":"stop","prompt_eval_count":3,"eval_count":2}\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    install_transport(monkeypatch, handler)
    events = list(
        complete_stream(
            CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
        )
    )
    texts = [e.text for e in events if e.kind == "delta"]
    assert texts == ["Hel", "lo"]
    usage = [e for e in events if e.kind == "usage"]
    assert usage
    assert usage[-1].usage is not None
    assert usage[-1].usage.completion_tokens == 2
    assert events[-1].kind == "done"
    assert events[-1].finish_reason == "stop"


def test_gpu_max_in_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=_chat_ok())

    install_transport(monkeypatch, handler)
    complete(CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG))
    assert seen[0]["options"]["num_gpu"] == 16


def test_gpu_max_falls_back_to_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        seen.append(body.get("options") or {})
        if len(seen) == 1:
            return httpx.Response(500, json={"error": "not enough memory to load model"})
        return httpx.Response(200, json=_chat_ok())

    install_transport(monkeypatch, handler)
    result = complete(
        CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
    )
    assert result.content == "hello"
    assert seen[0]["num_gpu"] == 16
    assert seen[1]["num_gpu"] == -1


def test_gpu_cpu_forced_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"error": "not enough memory to load model"})

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as err:
        complete(
            CompletionRequest(
                provider="ollama",
                model="llama3.2:1b",
                messages=_MSG,
                ollama_options={"num_gpu": 0},
            )
        )
    assert err.value.error_key == "runtime.upstream"
    assert calls["n"] == 1


def test_explicit_num_gpu_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=_chat_ok())

    install_transport(monkeypatch, handler)
    complete(
        CompletionRequest(
            provider="ollama",
            model="llama3.2:1b",
            messages=_MSG,
            ollama_options={"num_gpu": 8},
        )
    )
    assert seen[0]["options"]["num_gpu"] == 8


def test_num_thread_in_ollama_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=_chat_ok())

    install_transport(monkeypatch, handler)
    complete(
        CompletionRequest(
            provider="ollama",
            model="llama3.2:1b",
            messages=_MSG,
            ollama_options={"num_thread": 6, "num_ctx": 8192},
        )
    )
    options = seen[0]["options"]
    assert options["num_thread"] == 6
    assert options["num_ctx"] == 8192
    assert options["num_gpu"] == 16


def test_stream_gpu_fallback_before_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []
    payload = (
        b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        seen.append(body.get("options") or {})
        if len(seen) == 1:
            return httpx.Response(500, json={"error": "failed to load model into vram"})
        return httpx.Response(200, content=payload)

    install_transport(monkeypatch, handler)
    events = list(
        complete_stream(
            CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG)
        )
    )
    assert seen[0]["num_gpu"] == 16
    assert seen[1]["num_gpu"] == -1
    texts = [e.text for e in events if e.kind == "delta"]
    assert texts == ["ok"]


_WRITE_ARGS = '{"action":"write","path":"geschichte-ueber-eine-biene.txt"}'


def _tool_followup_messages(*, call_id: str = "", tool_name: str | None = None) -> list[ChatMessage]:
    return [
        ChatMessage(role="user", content="speichere den text"),
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(id=call_id, name="file_access", arguments=_WRITE_ARGS),
            ],
        ),
        ChatMessage(
            role="tool",
            content='{"ok":true,"bytes":1631}',
            tool_call_id=call_id or None,
            name=tool_name,
        ),
    ]


def test_ollama_tool_followup_uses_native_shape() -> None:
    messages = _ollama_messages(_tool_followup_messages())
    assistant = messages[1]
    tool = messages[2]
    call = assistant["tool_calls"][0]
    assert assistant["content"] == ""
    assert "id" not in call
    assert call["type"] == "function"
    assert call["function"]["name"] == "file_access"
    assert call["function"]["arguments"] == {
        "action": "write",
        "path": "geschichte-ueber-eine-biene.txt",
    }
    assert tool["role"] == "tool"
    assert tool["tool_name"] == "file_access"
    assert "tool_call_id" not in tool
    assert "name" not in tool


def test_openai_tool_followup_keeps_string_arguments() -> None:
    messages = _openai_messages(_tool_followup_messages(call_id="c1", tool_name="file_access"))
    call = messages[1]["tool_calls"][0]
    tool = messages[2]
    assert call["id"] == "c1"
    assert call["type"] == "function"
    assert call["function"]["arguments"] == _WRITE_ARGS
    assert tool["tool_call_id"] == "c1"
    assert tool["name"] == "file_access"
    assert "tool_name" not in tool


def test_ollama_complete_sends_native_tool_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=_chat_ok())

    install_transport(monkeypatch, handler)
    complete(
        CompletionRequest(
            provider="ollama",
            model="llama3.2:1b",
            messages=_tool_followup_messages(),
        )
    )
    body = seen[0]
    call = body["messages"][1]["tool_calls"][0]
    tool = body["messages"][2]
    assert isinstance(call["function"]["arguments"], dict)
    assert call["function"]["arguments"]["action"] == "write"
    assert tool["tool_name"] == "file_access"
    assert "tool_call_id" not in tool


def test_xai_complete_keeps_openai_tool_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=_chat_ok())

    install_transport(monkeypatch, handler)
    complete(
        CompletionRequest(
            provider="xai",
            model="grok",
            messages=_tool_followup_messages(call_id="c1", tool_name="file_access"),
            secret="sk-test-secret",
        )
    )
    call = seen[0]["messages"][1]["tool_calls"][0]
    tool = seen[0]["messages"][2]
    assert isinstance(call["function"]["arguments"], str)
    assert tool["tool_call_id"] == "c1"
    assert "tool_name" not in tool
