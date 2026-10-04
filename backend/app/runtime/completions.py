"""Completions path. Ollama uses native /api/chat so options reach the daemon."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Generator, Iterator
from typing import Any

from app.common.http import client
from app.common.types import Provider
from app.runtime.errors import (
    RuntimeApiError,
    clip_error_detail,
    is_timeout_error,
    is_transport_error,
    map_http_status,
    raise_for_status,
    raise_transport,
    response_json,
    transport_error_key,
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
from app.runtime.ollama import model_block_count
from app.runtime.urls import completions_url, settings_roots

log = logging.getLogger("agentus.runtime")

_LOAD_FAIL_MARKERS = (
    "memory",
    "vram",
    "out of memory",
    "oom",
    "failed to load",
    "unable to load",
    "load model",
    "model failed",
    "cuda",
    "hip error",
    "ggml",
    "runner",
    "terminated",
    "killed",
    "insufficient",
)


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


def _ollama_arguments(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return {"raw": raw}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _ollama_tool_call(call: ToolCall, index: int) -> dict[str, Any]:
    item: dict[str, Any] = {
        "type": "function",
        "function": {
            "index": index,
            "name": call.name,
            "arguments": _ollama_arguments(call.arguments),
        },
    }
    if call.id:
        item["id"] = call.id
    return item


def _consume_tool_name(
    message: ChatMessage, pending: list[ToolCall], used: set[int]
) -> str | None:
    if message.tool_call_id:
        for index, call in enumerate(pending):
            if call.id and call.id == message.tool_call_id:
                used.add(index)
                return message.name or call.name or None
    for index, call in enumerate(pending):
        if index not in used:
            used.add(index)
            return message.name or call.name or None
    return message.name


def _ollama_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Native /api/chat history: arguments as objects, tool results via tool_name."""
    out: list[dict[str, Any]] = []
    pending: list[ToolCall] = []
    used: set[int] = set()
    for message in messages:
        item: dict[str, Any] = {"role": message.role}
        if message.content is not None:
            item["content"] = message.content
        elif message.tool_calls or message.role == "tool":
            item["content"] = ""
        if message.tool_calls:
            pending = list(message.tool_calls)
            used = set()
            item["tool_calls"] = [
                _ollama_tool_call(call, index)
                for index, call in enumerate(message.tool_calls)
            ]
        if message.role == "tool":
            name = _consume_tool_name(message, pending, used)
            if name:
                item["tool_name"] = name
        out.append(item)
    return out


def _apply_gpu_max(req: CompletionRequest, options: dict[str, Any]) -> dict[str, Any]:
    if "num_gpu" in options:
        return options
    layers = model_block_count(req.model, base_url=req.base_url)
    options["num_gpu"] = layers if layers else 999
    return options


def _ollama_payload(req: CompletionRequest, *, stream: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": req.model,
        "messages": _ollama_messages(req.messages),
        "stream": stream,
    }
    options = dict(req.ollama_options or {})
    if req.temperature is not None:
        options["temperature"] = req.temperature
    if req.max_tokens is not None:
        options["num_predict"] = req.max_tokens
    options = _apply_gpu_max(req, options)
    if options:
        body["options"] = options
    if req.tools:
        body["tools"] = req.tools
    return body


def _payload(req: CompletionRequest, *, stream: bool) -> dict[str, Any]:
    if req.provider == "ollama":
        return _ollama_payload(req, stream=stream)
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
    if stream:
        body["stream_options"] = {"include_usage": True}
    return body


def _payload_num_gpu(payload: dict[str, Any]) -> int | None:
    options = payload.get("options")
    if not isinstance(options, dict) or "num_gpu" not in options:
        return None
    try:
        return int(options["num_gpu"])
    except (TypeError, ValueError):
        return None


def _looks_like_load_fail(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in _LOAD_FAIL_MARKERS)


def _can_retry_gpu(payload: dict[str, Any], status: int, text: str) -> bool:
    gpu = _payload_num_gpu(payload)
    if gpu is None or gpu <= 0:
        return False
    if status not in {200, 400, 500, 503}:
        return False
    return _looks_like_load_fail(text)


def _retry_gpu_auto(req: CompletionRequest) -> CompletionRequest:
    options = dict(req.ollama_options or {})
    options["num_gpu"] = -1
    return req.model_copy(update={"ollama_options": options})


def _read_body(response: Any) -> str:
    try:
        data = response.read()
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data or "")
    except Exception:
        try:
            return str(response.text or "")
        except Exception:
            return ""


def _stream_error(error_key: str, detail: str | None = None) -> StreamEvent:
    clipped = clip_error_detail(detail)
    if clipped:
        log.warning("completion error key=%s detail=%s", error_key, clipped)
    return StreamEvent(kind="error", error_key=error_key, error_detail=clipped)


def _chunk_error_text(chunk: dict[str, Any]) -> str:
    raw = chunk.get("error")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        for key in ("message", "error", "detail"):
            value = raw.get(key)
            if isinstance(value, str) and value:
                return value
        try:
            return json.dumps(raw)
        except (TypeError, ValueError):
            return str(raw)
    return ""


def _tool_arguments(raw: object) -> str:
    if isinstance(raw, str):
        return raw
    try:
        return json.dumps(raw or {})
    except (TypeError, ValueError):
        return "{}"


def _parse_tool_calls(raw: object) -> list[ToolCall]:
    if not isinstance(raw, list):
        return []
    calls: list[ToolCall] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else {}
        calls.append(
            ToolCall(
                id=str(item.get("id") or ""),
                name=str(fn.get("name") or ""),
                arguments=_tool_arguments(fn.get("arguments")),
            )
        )
    return calls


def _int_field(raw: dict[str, Any], *names: str) -> int | None:
    for name in names:
        if name not in raw or raw[name] is None:
            continue
        try:
            return int(raw[name])
        except (TypeError, ValueError):
            continue
    return None


def _parse_usage(raw: object) -> CompletionUsage | None:
    if not isinstance(raw, dict):
        return None
    prompt = _int_field(raw, "prompt_tokens", "input_tokens", "prompt_eval_count")
    completion = _int_field(raw, "completion_tokens", "output_tokens", "eval_count")
    if prompt is None and completion is None:
        return None
    return CompletionUsage(prompt_tokens=prompt or 0, completion_tokens=completion or 0)


def _usage_nonzero(usage: CompletionUsage | None) -> bool:
    return bool(usage and (usage.prompt_tokens or usage.completion_tokens))


def _delta_reasoning(delta: dict[str, Any]) -> str:
    for key in ("reasoning", "reasoning_content", "thinking"):
        value = delta.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def estimate_token_count(text: str) -> int:
    """Cheap live estimate until the provider sends ``usage`` (~4 chars/token)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _message_content(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if content is None:
        return None
    if isinstance(content, str):
        return content
    return str(content)


def _result_from_body(body: object, req: CompletionRequest) -> CompletionResult:
    if not isinstance(body, dict):
        raise RuntimeApiError("runtime.badRequest", detail="invalid completion body")
    err_text = _chunk_error_text(body)
    if err_text:
        raise RuntimeApiError("runtime.badRequest", detail=err_text)
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        finish = first.get("finish_reason") if isinstance(first.get("finish_reason"), str) else None
        return CompletionResult(
            content=_message_content(message) if message else None,
            tool_calls=_parse_tool_calls(message.get("tool_calls")),
            finish_reason=finish,
            usage=_parse_usage(body.get("usage")) or _parse_usage(body),
            model=str(body.get("model") or req.model),
        )
    message = body.get("message") if isinstance(body.get("message"), dict) else None
    if message is None:
        raise RuntimeApiError("runtime.badRequest")
    finish = body.get("done_reason") if isinstance(body.get("done_reason"), str) else None
    return CompletionResult(
        content=_message_content(message),
        tool_calls=_parse_tool_calls(message.get("tool_calls")),
        finish_reason=finish,
        usage=_parse_usage(body.get("usage")) or _parse_usage(body),
        model=str(body.get("model") or req.model),
    )


def complete(req: CompletionRequest) -> CompletionResult:
    secret = _auth_secret(req.provider, req.secret, req.credential_id)
    url = _endpoint(req.provider, req.base_url)
    headers = request_headers(req.provider, secret)
    current = req
    last_status = 0
    last_text = ""
    for attempt in range(2):
        payload = _payload(current, stream=False)
        try:
            with client(timeout_sec=req.timeout_sec) as http:
                response = http.post(url, json=payload, headers=headers)
            last_status = response.status_code
            if response.status_code != 200:
                last_text = response.text or ""
                if attempt == 0 and _can_retry_gpu(payload, response.status_code, last_text):
                    log.info("ollama gpu max failed, retrying with auto model=%s", req.model)
                    current = _retry_gpu_auto(current)
                    continue
                raise_for_status(response)
            body = response_json(response)
        except RuntimeApiError:
            raise
        except Exception as exc:
            if is_transport_error(exc):
                raise_transport(exc)
            raise
        err_text = _chunk_error_text(body) if isinstance(body, dict) else ""
        if err_text:
            last_text = err_text
            last_status = last_status or 500
            if attempt == 0 and _can_retry_gpu(payload, last_status, last_text):
                log.info("ollama gpu max failed, retrying with auto model=%s", req.model)
                current = _retry_gpu_auto(current)
                continue
            raise RuntimeApiError("runtime.badRequest", detail=last_text)
        return _result_from_body(body, current)
    raise RuntimeApiError(
        map_http_status(last_status or 500),
        status=last_status or None,
        detail=last_text,
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
        if "arguments" in fn and fn["arguments"] is not None:
            raw_args = fn["arguments"]
            if isinstance(raw_args, str):
                slot["arguments"] += raw_args
            else:
                slot["arguments"] = _tool_arguments(raw_args)
    return [
        ToolCall(id=slot["id"], name=slot["name"], arguments=slot["arguments"])
        for _, slot in sorted(acc.items())
    ]


def _emit_openai_chunk(
    chunk: dict[str, Any], acc: dict[int, dict[str, str]]
) -> tuple[list[StreamEvent], str | None]:
    events: list[StreamEvent] = []
    finish: str | None = None
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return events, finish
    first = choices[0] if isinstance(choices[0], dict) else {}
    if isinstance(first.get("finish_reason"), str):
        finish = first["finish_reason"]
    delta = first.get("delta") if isinstance(first.get("delta"), dict) else {}
    piece = delta.get("content")
    reasoning = _delta_reasoning(delta)
    if (isinstance(piece, str) and piece) or reasoning:
        events.append(
            StreamEvent(
                kind="delta",
                text=piece if isinstance(piece, str) and piece else None,
                reasoning=reasoning or None,
            )
        )
    if delta.get("tool_calls"):
        calls = _accumulate_tool_delta(acc, delta.get("tool_calls"))
        events.append(StreamEvent(kind="tool_call_delta", tool_calls=calls))
    return events, finish


def _emit_native_chunk(
    chunk: dict[str, Any], acc: dict[int, dict[str, str]]
) -> tuple[list[StreamEvent], str | None]:
    events: list[StreamEvent] = []
    finish: str | None = None
    message = chunk.get("message") if isinstance(chunk.get("message"), dict) else None
    if message is not None:
        piece = message.get("content")
        reasoning = _delta_reasoning(message)
        if (isinstance(piece, str) and piece) or reasoning:
            events.append(
                StreamEvent(
                    kind="delta",
                    text=piece if isinstance(piece, str) and piece else None,
                    reasoning=reasoning or None,
                )
            )
        if message.get("tool_calls"):
            calls = _accumulate_tool_delta(acc, message.get("tool_calls"))
            events.append(StreamEvent(kind="tool_call_delta", tool_calls=calls))
    if chunk.get("done") is True:
        finish = chunk.get("done_reason") if isinstance(chunk.get("done_reason"), str) else "stop"
    return events, finish


def complete_stream(req: CompletionRequest) -> Iterator[StreamEvent]:
    try:
        secret = _auth_secret(req.provider, req.secret, req.credential_id)
        url = _endpoint(req.provider, req.base_url)
        headers = request_headers(req.provider, secret)
    except RuntimeApiError as exc:
        yield StreamEvent(kind="error", error_key=exc.error_key)
        return
    current = req
    for attempt in range(2):
        payload = _payload(current, stream=True)
        outcome = yield from _stream_once(url, headers, payload, current)
        if outcome == "retry" and attempt == 0:
            log.info("ollama gpu max failed, retrying with auto model=%s", req.model)
            current = _retry_gpu_auto(current)
            continue
        return


def _stream_once(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    req: CompletionRequest,
) -> Generator[StreamEvent, None, str]:
    acc: dict[int, dict[str, str]] = {}
    usage: CompletionUsage | None = None
    finish: str | None = None
    emitted = False
    try:
        with client(timeout_sec=req.timeout_sec) as http:
            with http.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    err_text = _read_body(response)
                    if _can_retry_gpu(payload, response.status_code, err_text):
                        return "retry"
                    yield _stream_error(map_http_status(response.status_code), err_text)
                    return "done"
                for line in response.iter_lines():
                    text = line.decode("utf-8") if isinstance(line, bytes) else str(line)
                    text = text.strip()
                    if not text:
                        continue
                    if text.startswith("data:"):
                        data = text[5:].strip()
                    elif text.startswith("{"):
                        data = text
                    else:
                        continue
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except ValueError:
                        if text.startswith("data:"):
                            yield _stream_error("runtime.badRequest", "invalid stream json")
                            return "done"
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    err_text = _chunk_error_text(chunk)
                    if err_text:
                        if not emitted and _can_retry_gpu(payload, 500, err_text):
                            return "retry"
                        yield _stream_error("runtime.badRequest", err_text)
                        return "done"
                    chunk_usage = _parse_usage(chunk.get("usage")) or _parse_usage(chunk)
                    if _usage_nonzero(chunk_usage):
                        usage = chunk_usage
                        emitted = True
                        yield StreamEvent(kind="usage", usage=usage)
                    openai_events, openai_finish = _emit_openai_chunk(chunk, acc)
                    native_events, native_finish = ([], None)
                    if not openai_events and openai_finish is None:
                        native_events, native_finish = _emit_native_chunk(chunk, acc)
                    for event in openai_events or native_events:
                        emitted = True
                        yield event
                    if openai_finish:
                        finish = openai_finish
                    elif native_finish:
                        finish = native_finish
    except RuntimeApiError as exc:
        yield _stream_error(exc.error_key, exc.detail)
        return "done"
    except Exception as exc:
        if is_timeout_error(exc) or is_transport_error(exc):
            yield _stream_error(transport_error_key(exc), f"{type(exc).__name__}: {exc}")
            return "done"
        yield _stream_error("runtime.badRequest", f"{type(exc).__name__}: {exc}")
        return "done"
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
    return "done"


def complete_live(
    req: CompletionRequest,
    *,
    should_abort: Callable[[], bool] | None = None,
    on_progress: Callable[[int, float], None] | None = None,
) -> CompletionResult:
    """Stream a completion. ``timeout_sec`` is idle time without a chunk, not total duration."""
    texts: list[str] = []
    reasons: list[str] = []
    tool_calls: list[ToolCall] = []
    usage: CompletionUsage | None = None
    finish: str | None = None
    estimated_out = 0
    started = time.perf_counter()
    last_progress = 0.0
    emitted_progress = False

    def _estimate() -> int:
        return estimate_token_count("".join(texts)) + estimate_token_count("".join(reasons))

    def _emit(out: int) -> None:
        nonlocal last_progress, emitted_progress
        if on_progress is None:
            return
        now = time.perf_counter()
        if emitted_progress and now - last_progress < 0.25:
            return
        elapsed = max(now - started, 0.05)
        last_progress = now
        emitted_progress = True
        on_progress(out, out / elapsed)

    for event in complete_stream(req):
        if should_abort and should_abort():
            raise RuntimeApiError("run.cancelled")
        if event.kind == "delta":
            if event.text:
                texts.append(event.text)
            if event.reasoning:
                reasons.append(event.reasoning)
            estimated_out = _estimate()
            live = usage.completion_tokens if (usage and usage.completion_tokens) else estimated_out
            if live:
                _emit(live)
        elif event.kind == "tool_call_delta" and event.tool_calls:
            tool_calls = event.tool_calls
        elif event.kind == "usage" and _usage_nonzero(event.usage):
            usage = event.usage
            live = usage.completion_tokens if usage and usage.completion_tokens else estimated_out
            if live:
                _emit(live)
        elif event.kind == "error":
            raise RuntimeApiError(
                event.error_key or "runtime.badRequest",
                detail=event.error_detail,
            )
        elif event.kind == "done":
            if event.tool_calls:
                tool_calls = event.tool_calls
            if _usage_nonzero(event.usage):
                usage = event.usage
            finish = event.finish_reason
    estimated_out = _estimate()
    if usage is None or (usage.completion_tokens == 0 and estimated_out):
        usage = CompletionUsage(
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=estimated_out,
        )
    out = usage.completion_tokens if usage and usage.completion_tokens else estimated_out
    if on_progress is not None and out:
        elapsed = max(time.perf_counter() - started, 0.05)
        on_progress(out, out / elapsed)
    return CompletionResult(
        content="".join(texts) or None,
        reasoning="".join(reasons) or None,
        tool_calls=tool_calls,
        finish_reason=finish,
        usage=usage if _usage_nonzero(usage) else None,
        model=req.model,
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
