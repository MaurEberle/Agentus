from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.runtime.completions import (
    _parse_usage,
    complete,
    complete_live,
    complete_stream,
    estimate_token_count,
)
from app.runtime.errors import RuntimeApiError
from app.runtime.models import ChatMessage, CompletionRequest
from tests.runtime.transport import install_transport

_MSG = [ChatMessage(role="user", content="hi")]


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
        assert body["stream_options"] == {"include_usage": True}
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
        assert body["stream_options"] == {"include_usage": True}
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
