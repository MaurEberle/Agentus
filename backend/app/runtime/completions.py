"""One OpenAI-compatible completions path. Help and harness import this."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from app.common.http import client
from app.common.types import Provider
from app.runtime.errors import (
    RuntimeApiError,
    is_transport_error,
    map_http_status,
    raise_for_status,
    raise_transport,
    response_json,
)
from app.runtime.models import (
    ChatMessage,
    CompletionRequest,
    CompletionResult,
    CompletionUsage,
    PingResult,
    StreamEvent,
    TestLlmRequest,
    ToolCall,
)
from app.runtime.urls import completions_url, settings_roots


def resolve_secret(req_secret: str | None, credential_id: str | None) -> str | None:
    if req_secret:
        return req_secret
    if credential_id:
        from app.db.vault import get as vault_get

        return vault_get(credential_id)
    return None


ANTHROPIC_VERSION = "2023-06-01"


def request_headers(provider: Provider, secret: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if provider == "ollama" or not secret:
        return headers
    headers["Authorization"] = f"Bearer {secret}"
    if provider == "anthropic":
        headers["x-api-key"] = secret
        headers["anthropic-version"] = ANTHROPIC_VERSION
    return headers


def _auth_secret(provider: Provider, secret: str | None, credential_id: str | None) -> str | None:
    if provider == "ollama":
        return None
    resolved = resolve_secret(secret, credential_id)
    if not resolved:
        raise RuntimeApiError("runtime.missingCredential")
    return resolved


def _endpoint(
    provider: Provider, override_base: str | None, *, embeddings: bool = False
) -> str:
    ollama_root, openai_base = settings_roots()
    from app.runtime.urls import embeddings_url

    fn = embeddings_url if embeddings else completions_url
    return fn(
        provider,
        ollama_root=ollama_root,
        override_base=override_base,
        settings_openai=openai_base,
    )


def _openai_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        item: dict[str, Any] = {"role": message.role}
        if message.content is not None:
            item["content"] = message.content
        if message.name:
            item["name"] = message.name
        if message.tool_call_id:
            item["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in message.tool_calls
            ]
        out.append(item)
    return out


def _payload(req: CompletionRequest, *, stream: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": req.model,
        "messages": _openai_messages(req.messages),
        "stream": stream,
    }
    if req.temperature is not None:
        body["temperature"] = req.temperature
    if req.max_tokens is not None:
        body["max_tokens"] = req.max_tokens
    if req.tools:
        body["tools"] = req.tools
    if req.provider == "ollama" and req.ollama_options:
        body["options"] = req.ollama_options
    return body


def _parse_tool_calls(raw: object) -> list[ToolCall]:
    if not isinstance(raw, list):
        return []
    calls: list[ToolCall] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else {}
        arguments = fn.get("arguments")
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments or {})
        calls.append(
            ToolCall(
                id=str(item.get("id") or ""),
                name=str(fn.get("name") or ""),
                arguments=arguments,
            )
        )
    return calls


def _parse_usage(raw: object) -> CompletionUsage | None:
    if not isinstance(raw, dict):
        return None
    if "prompt_tokens" not in raw or "completion_tokens" not in raw:
        return None
    try:
        return CompletionUsage(
            prompt_tokens=int(raw["prompt_tokens"]),
            completion_tokens=int(raw["completion_tokens"]),
        )
    except (TypeError, ValueError):
        return None


def complete(req: CompletionRequest) -> CompletionResult:
    secret = _auth_secret(req.provider, req.secret, req.credential_id)
    url = _endpoint(req.provider, req.base_url)
    headers = request_headers(req.provider, secret)
    try:
        with client(timeout_sec=req.timeout_sec) as http:
            response = http.post(url, json=_payload(req, stream=False), headers=headers)
        raise_for_status(response)
        body = response_json(response)
    except RuntimeApiError:
        raise
    except Exception as exc:
        if is_transport_error(exc):
            raise_transport(exc)
        raise
    if not isinstance(body, dict):
        raise RuntimeApiError("runtime.badRequest")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeApiError("runtime.badRequest")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        content = str(content)
    return CompletionResult(
        content=content,
        tool_calls=_parse_tool_calls(message.get("tool_calls")),
        finish_reason=first.get("finish_reason")
        if isinstance(first.get("finish_reason"), str)
        else None,
        usage=_parse_usage(body.get("usage")),
        model=str(body.get("model") or req.model),
    )


def _accumulate_tool_delta(
    acc: dict[int, dict[str, str]], raw: object
) -> list[ToolCall]:
    if not isinstance(raw, list):
        return [ToolCall(id=v["id"], name=v["name"], arguments=v["arguments"]) for v in acc.values()]
    for item in raw:
        if not isinstance(item, dict):
            continue
        index = int(item.get("index") or 0)
        slot = acc.setdefault(index, {"id": "", "name": "", "arguments": ""})
        if item.get("id"):
            slot["id"] = str(item["id"])
        fn = item.get("function") if isinstance(item.get("function"), dict) else {}
        if fn.get("name"):
            slot["name"] = str(fn["name"])
        if fn.get("arguments"):
            slot["arguments"] += str(fn["arguments"])
    return [
        ToolCall(id=slot["id"], name=slot["name"], arguments=slot["arguments"])
        for _, slot in sorted(acc.items())
    ]


def complete_stream(req: CompletionRequest) -> Iterator[StreamEvent]:
    try:
        secret = _auth_secret(req.provider, req.secret, req.credential_id)
        url = _endpoint(req.provider, req.base_url)
        headers = request_headers(req.provider, secret)
    except RuntimeApiError as exc:
        yield StreamEvent(kind="error", error_key=exc.error_key)
        return
    acc: dict[int, dict[str, str]] = {}
    usage: CompletionUsage | None = None
    finish: str | None = None
    try:
        with client(timeout_sec=req.timeout_sec) as http:
            with http.stream(
                "POST",
                url,
                json=_payload(req, stream=True),
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    yield StreamEvent(
                        kind="error",
                        error_key=map_http_status(response.status_code),
                    )
                    return
                for line in response.iter_lines():
                    text = line.decode("utf-8") if isinstance(line, bytes) else str(line)
                    text = text.strip()
                    if not text.startswith("data:"):
                        continue
                    data = text[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        yield StreamEvent(kind="error", error_key="runtime.badRequest")
                        return
                    if not isinstance(chunk, dict):
                        continue
                    chunk_usage = _parse_usage(chunk.get("usage"))
                    if chunk_usage is not None:
                        usage = chunk_usage
                        yield StreamEvent(kind="usage", usage=usage)
                    choices = chunk.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    first = choices[0] if isinstance(choices[0], dict) else {}
                    if isinstance(first.get("finish_reason"), str):
                        finish = first["finish_reason"]
                    delta = first.get("delta") if isinstance(first.get("delta"), dict) else {}
                    piece = delta.get("content")
                    if isinstance(piece, str) and piece:
                        yield StreamEvent(kind="delta", text=piece)
                    if delta.get("tool_calls"):
                        calls = _accumulate_tool_delta(acc, delta.get("tool_calls"))
                        yield StreamEvent(kind="tool_call_delta", tool_calls=calls)
    except RuntimeApiError as exc:
        yield StreamEvent(kind="error", error_key=exc.error_key)
        return
    except Exception as exc:
        if is_transport_error(exc):
            yield StreamEvent(kind="error", error_key="runtime.unreachable")
            return
        yield StreamEvent(kind="error", error_key="runtime.badRequest")
        return
    yield StreamEvent(
        kind="done",
        finish_reason=finish,
        tool_calls=[
            ToolCall(id=slot["id"], name=slot["name"], arguments=slot["arguments"])
            for _, slot in sorted(acc.items())
        ]
        or None,
        usage=usage,
    )


def test_llm(req: TestLlmRequest) -> PingResult:
    completion = CompletionRequest(
        provider=req.provider,
        model=req.model,
        messages=[ChatMessage(role="user", content="ping")],
        base_url=req.base_url,
        credential_id=req.credential_id,
        max_tokens=1,
        timeout_sec=15.0,
    )
    try:
        complete(completion)
    except RuntimeApiError as exc:
        return PingResult(ok=False, message_key=exc.error_key)
    return PingResult(ok=True)
