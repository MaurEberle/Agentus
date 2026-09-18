from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.runtime.completions import complete, complete_stream
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
