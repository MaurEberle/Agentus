"""H9: parallel native tool calls stay separate. H11: HTTP 429 waits and is retried."""

from __future__ import annotations

import json

import httpx
import pytest

from app.runtime.completions import complete, complete_live, complete_stream
from app.runtime.errors import (
    RuntimeApiError,
    map_http_status,
    rate_limit_wait,
    retry_after_seconds,
)
from app.runtime.models import ChatMessage, CompletionRequest, EmbedRequest
from tests.runtime.transport import install_transport

_MSG = [ChatMessage(role="user", content="hi")]


@pytest.fixture(autouse=True)
def _stub_block_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.runtime.completions.model_block_count", lambda *a, **k: 16)
    monkeypatch.setattr("app.runtime.completions.model_is_moe", lambda *a, **k: False)


def _native(lines: list[dict]) -> bytes:
    return ("\n".join(json.dumps(line) for line in lines) + "\n").encode("utf-8")


def _stream(monkeypatch: pytest.MonkeyPatch, body: bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    install_transport(monkeypatch, handler)
    return complete_live(CompletionRequest(provider="ollama", model="llama3.2:1b", messages=_MSG))


def _read(path: str) -> dict:
    return {"function": {"name": "file_access", "arguments": {"action": "read", "path": path}}}


def test_two_native_calls_in_one_chunk_stay_two(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _native(
        [
            {"message": {"role": "assistant", "content": "", "tool_calls": [_read("a.txt"), _read("b.txt")]}},
            {"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop"},
        ]
    )
    result = _stream(monkeypatch, body)
    paths = [json.loads(call.arguments)["path"] for call in result.tool_calls]
    # H9: both used to land in slot 0 and only b.txt survived.
    assert paths == ["a.txt", "b.txt"]


def test_native_calls_with_function_index_and_across_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    second = _read("b.txt")
    second["function"]["index"] = 1
    third = _read("c.txt")
    third["id"] = "call_3"
    body = _native(
        [
            {"message": {"role": "assistant", "content": "", "tool_calls": [_read("a.txt")]}},
            {"message": {"role": "assistant", "content": "", "tool_calls": [second]}},
            {"message": {"role": "assistant", "content": "", "tool_calls": [third]}},
            {"message": {"role": "assistant", "content": ""}, "done": True},
        ]
    )
    result = _stream(monkeypatch, body)
    assert [json.loads(call.arguments)["path"] for call in result.tool_calls] == ["a.txt", "b.txt", "c.txt"]
    assert result.tool_calls[2].id == "call_3"


def test_openai_fragments_still_merge_into_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def chunk(delta: dict) -> bytes:
        return b"data: " + json.dumps({"choices": [{"delta": delta}]}).encode("utf-8") + b"\n\n"

    body = (
        chunk({"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "file_access", "arguments": '{"action":'}}]})
        + chunk({"tool_calls": [{"index": 0, "function": {"arguments": '"list","path":"."}'}}]})
        + chunk({"tool_calls": [{"index": 1, "id": "c2", "function": {"name": "datetime", "arguments": "{}"}}]})
        + b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    install_transport(monkeypatch, handler)
    result = complete_live(
        CompletionRequest(provider="xai", model="grok", messages=_MSG, secret="sk-test-000000000000")
    )
    assert [(call.id, call.name, call.arguments) for call in result.tool_calls] == [
        ("c1", "file_access", '{"action":"list","path":"."}'),
        ("c2", "datetime", "{}"),
    ]


def test_fragments_without_index_continue_the_same_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def chunk(delta: dict) -> bytes:
        return b"data: " + json.dumps({"choices": [{"delta": delta}]}).encode("utf-8") + b"\n\n"

    body = (
        chunk({"tool_calls": [{"id": "c1", "function": {"name": "file_access", "arguments": '{"action":'}}]})
        + chunk({"tool_calls": [{"function": {"arguments": '"list"}'}}]})
        + b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    install_transport(monkeypatch, handler)
    result = complete_live(
        CompletionRequest(provider="xai", model="grok", messages=_MSG, secret="sk-test-000000000000")
    )
    assert [(call.id, call.arguments) for call in result.tool_calls] == [("c1", '{"action":"list"}')]


def test_429_is_its_own_key() -> None:
    assert map_http_status(429) == "runtime.rateLimited"
    assert map_http_status(400) == "runtime.badRequest"


def test_retry_after_forms() -> None:
    assert retry_after_seconds(httpx.Headers({"retry-after": "7"})) == 7.0
    assert retry_after_seconds(httpx.Headers({"retry-after-ms": "1500"})) == 1.5
    assert retry_after_seconds(httpx.Headers({})) is None
    assert retry_after_seconds(httpx.Headers({"retry-after": "soon"})) is None
    # A wait the provider names is used; a very long one is not sat out.
    assert rate_limit_wait(7.0, 0) == 7.0
    assert rate_limit_wait(600.0, 0) is None
    assert rate_limit_wait(None, 0) == 2.0 and rate_limit_wait(None, 9) == 10.0


def test_stream_waits_and_retries_after_429(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr(
        "app.runtime.completions._wait_abortable", lambda seconds, abort: waits.append(seconds) or False
    )
    calls = {"n": 0}
    ok = b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(429, headers={"retry-after": "3"}, json={"error": "slow down"})
        return httpx.Response(200, content=ok)

    install_transport(monkeypatch, handler)
    result = complete_live(
        CompletionRequest(provider="xai", model="grok", messages=_MSG, secret="sk-test-000000000000")
    )
    assert result.content == "ok"
    assert calls["n"] == 3
    assert waits == [3.0, 3.0]


def test_stream_gives_up_after_the_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.runtime.completions._wait_abortable", lambda seconds, abort: False)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": "slow down"})

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as caught:
        complete_live(
            CompletionRequest(provider="xai", model="grok", messages=_MSG, secret="sk-test-000000000000")
        )
    assert caught.value.error_key == "runtime.rateLimited"
    # One call plus three retries.
    assert calls["n"] == 4


def test_stop_during_the_wait_ends_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    stopped = {"now": False}

    def handler(request: httpx.Request) -> httpx.Response:
        stopped["now"] = True
        return httpx.Response(429, headers={"retry-after": "30"}, json={"error": "slow down"})

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as caught:
        complete_live(
            CompletionRequest(provider="xai", model="grok", messages=_MSG, secret="sk-test-000000000000"),
            should_abort=lambda: stopped["now"],
        )
    assert caught.value.error_key == "run.cancelled"


def test_plain_complete_reports_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "12"}, json={"error": "slow down"})

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as caught:
        complete(CompletionRequest(provider="xai", model="grok", messages=_MSG, secret="sk-test-000000000000"))
    assert caught.value.error_key == "runtime.rateLimited"
    assert caught.value.retry_after == 12.0


def test_embedding_batch_is_repeated_after_429(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    from app.runtime.embeddings import embed

    waits: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: waits.append(seconds))
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "1"}, json={"error": "slow down"})
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 0.0]}]})

    install_transport(monkeypatch, handler)
    result = embed(EmbedRequest(texts=["x"], model="text-embedding-3-small", provider="openai", secret="sk-test-000000000000"))
    assert result.dimension == 2
    assert calls["n"] == 2
    assert waits == [1.0]
