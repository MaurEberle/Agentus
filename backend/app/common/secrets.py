"""Mask secrets in logs, RAG, SSE, and tool results. One implementation."""

from __future__ import annotations

import re
from typing import Any

_BEARER_RE = re.compile(r"(?i)\b(Bearer)\s+\S+")
_SK_RE = re.compile(r"\bsk-[A-Za-z0-9\-_]{8,}")
_SECRET_KEYS = frozenset(
    {
        "apikey",
        "api_key",
        "token",
        "password",
        "authorization",
        "secret",
    }
)
_MAX_DEPTH = 8


def mask_text(value: str) -> str:
    """Redact Bearer tokens and ``sk-`` key substrings; keep the rest of the string."""
    masked = _BEARER_RE.sub(lambda m: f"{m.group(1)} ***", value)
    return _SK_RE.sub("sk-***", masked)


def mask_obj(value: object, *, _depth: int = 0) -> object:
    """Recursively mask dict/list/tuple/str. Secret keys become ``\"***\"``."""
    if _depth >= _MAX_DEPTH:
        return "***"
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        out: dict[Any, object] = {}
        for key, nested in value.items():
            if _is_secret_key(key):
                out[key] = "***"
            else:
                out[key] = mask_obj(nested, _depth=_depth + 1)
        return out
    if isinstance(value, list):
        return [mask_obj(item, _depth=_depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_obj(item, _depth=_depth + 1) for item in value)
    return value


def _is_secret_key(key: object) -> bool:
    return isinstance(key, str) and key.lower() in _SECRET_KEYS
