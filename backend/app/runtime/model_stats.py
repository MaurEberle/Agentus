"""Context-window stats for one selected model."""

from __future__ import annotations

from typing import Any

from app.common.http import client
from app.common.types import Provider
from app.runtime.completions import request_headers, resolve_secret
from app.runtime.errors import (
    RuntimeApiError,
    is_transport_error,
    raise_for_status,
    raise_transport,
    response_json,
)
from app.runtime.urls import models_url, settings_roots
from app.run.window import architecture_context

CLOUD_STEPS = (
    4096,
    8192,
    16384,
    32768,
    65536,
    131072,
    262144,
    500_000,
    1_048_576,
    2_000_000,
)

_PREFIX_MAX: tuple[tuple[str, int], ...] = (
    ("grok-4.20", 2_000_000),
    ("grok-4.3", 1_000_000),
    ("grok-4.5", 500_000),
    ("grok-code", 256_000),
    ("grok-4", 256_000),
    ("grok-3", 131_072),
    ("grok-2", 131_072),
    ("gpt-4.1", 1_048_576),
    ("gpt-4o", 128_000),
    ("gpt-4-turbo", 128_000),
    ("gpt-4", 8192),
    ("gpt-5", 1_048_576),
    ("gpt-3.5", 16_384),
    ("o3", 200_000),
    ("o1", 200_000),
    ("claude-opus-4", 200_000),
    ("claude-sonnet-4", 1_000_000),
    ("claude-3-7", 200_000),
    ("claude-3-5", 200_000),
    ("claude-3-opus", 200_000),
    ("claude-3-sonnet", 200_000),
    ("claude-3-haiku", 200_000),
    ("gemini-2.5", 1_048_576),
    ("gemini-2.0", 1_048_576),
    ("gemini-1.5-pro", 2_097_152),
    ("gemini-1.5", 1_048_576),
    ("gemini-pro", 32_768),
)

_INT_KEYS = (
    "context_length",
    "contextLength",
    "context_window",
    "contextWindow",
    "max_model_len",
    "max_context",
    "maxContext",
    "inputTokenLimit",
    "input_token_limit",
)


def context_steps(minimum: int, maximum: int) -> list[int]:
    lo = minimum if minimum > 0 else 1
    hi = maximum
    if hi < lo:
        hi = lo
    steps = [step for step in CLOUD_STEPS if lo <= step <= hi]
    if lo not in steps:
        steps.insert(0, lo)
    if hi not in steps:
        steps.append(hi)
    return sorted(set(steps))


def local_context_min(maximum: int) -> int:
    if maximum >= 4096:
        return 2048
    if maximum >= 1024:
        return 512
    return max(1, maximum)


def prefix_context_max(model: str) -> int | None:
    lowered = model.strip().lower()
    for prefix, size in _PREFIX_MAX:
        if lowered.startswith(prefix):
            return size
    return None


def extract_context_max(payload: object) -> int | None:
    found = _walk_context(payload)
    return found if found and found > 0 else None


def _walk_context(payload: object) -> int | None:
    if isinstance(payload, dict):
        info = payload.get("model_info")
        if isinstance(info, dict):
            best: int | None = None
            for key, value in info.items():
                if str(key).endswith("context_length") and isinstance(value, int) and value > 0:
                    best = value
            if best:
                return best
        for key in _INT_KEYS:
            value = payload.get(key)
            if isinstance(value, int) and value > 0:
                return value
            if isinstance(value, float) and value > 0:
                return int(value)
        for nested_key in ("data", "model", "limits", "capabilities"):
            nested = payload.get(nested_key)
            found = _walk_context(nested)
            if found:
                return found
        if isinstance(payload.get("data"), list) and len(payload["data"]) == 1:
            return _walk_context(payload["data"][0])
    if isinstance(payload, list) and len(payload) == 1:
        return _walk_context(payload[0])
    return None


def get_model_stats(
    provider: Provider,
    model: str,
    *,
    credential_id: str | None = None,
    base_url: str | None = None,
) -> tuple[int | None, int | None, list[int]]:
    tag = model.strip()
    if not tag:
        return None, None, []
    if provider == "ollama":
        maximum = architecture_context(tag, base_url=base_url)
        if maximum is None:
            return None, None, []
        minimum = local_context_min(maximum)
        return minimum, maximum, []
    maximum = _cloud_context_max(provider, tag, credential_id=credential_id, base_url=base_url)
    if maximum is None:
        maximum = prefix_context_max(tag)
    if maximum is None:
        return None, None, []
    minimum = 4096 if maximum >= 4096 else 1
    return minimum, maximum, context_steps(minimum, maximum)


def _cloud_context_max(
    provider: Provider,
    model: str,
    *,
    credential_id: str | None,
    base_url: str | None,
) -> int | None:
    try:
        secret = resolve_secret(None, credential_id)
    except RuntimeApiError:
        return None
    if not secret:
        return None
    ollama_root, openai_base = settings_roots()
    headers = request_headers(provider, secret)
    if provider == "gemini":
        native = _gemini_native_limit(model, secret)
        if native:
            return native
    base = models_url(
        provider,
        ollama_root=ollama_root,
        override_base=base_url,
        settings_openai=openai_base,
    )
    url = f"{base.rstrip('/')}/{model}"
    try:
        with client(timeout_sec=8.0) as http:
            response = http.get(url, headers=headers)
        raise_for_status(response)
        return extract_context_max(response_json(response))
    except RuntimeApiError:
        return None
    except Exception as exc:
        if is_transport_error(exc):
            raise_transport(exc)
        return None


def _gemini_native_limit(model: str, secret: str) -> int | None:
    name = model[len("models/") :] if model.startswith("models/") else model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{name}"
    headers = {
        "Authorization": f"Bearer {secret}",
        "x-goog-api-key": secret,
    }
    try:
        with client(timeout_sec=8.0) as http:
            response = http.get(url, headers=headers)
        raise_for_status(response)
        return extract_context_max(response_json(response))
    except Exception:
        return None
