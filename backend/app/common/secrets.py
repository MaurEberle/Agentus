"""Mask secrets in logs, RAG, SSE, and tool results. One implementation.

Two strengths:

- ``mask_text`` / ``mask_obj`` are broad. They are for text a person reads
  (logs, SSE, error messages): anything after ``Bearer`` goes.
- ``mask_content`` / ``mask_content_obj`` are narrow. They are for text a model
  reads and may write back (file contents, tool results). They only replace
  real secrets from the vault, well-known key formats, and a ``Bearer`` value
  that looks like a token. ``f"Bearer {token}"`` in source code stays intact.
"""

from __future__ import annotations

import json
import re
import threading
from typing import Any

_BEARER_RE = re.compile(r"(?i)\b(Bearer)\s+\S+")
# A real token after ``Bearer``: long, opaque, with letters and digits.
_BEARER_TOKEN_RE = re.compile(r"(?i)\b(Bearer)(\s+)([A-Za-z0-9._~+/=_-]{20,})")
_SK_RE = re.compile(r"\bsk-[A-Za-z0-9\-_]{8,}")
# Provider keys without the sk- prefix: Gemini (AIza...), xAI (xai-...), GitHub PATs.
_PROVIDER_KEY_RES = (
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}"), "AIza***"),
    (re.compile(r"\bxai-[A-Za-z0-9\-_]{16,}"), "xai-***"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "github_pat_***"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "gh*_***"),
)
_SECRET_KEYS = frozenset(
    {
        "apikey",
        "api_key",
        "token",
        "password",
        "authorization",
        "secret",
        "x-api-key",
        "x-goog-api-key",
        "accesstoken",
        "access_token",
        "refreshtoken",
        "refresh_token",
        "client_secret",
    }
)
_MAX_DEPTH = 8
# Tool results are data the model works with; do not blank deep structures.
_CONTENT_MAX_DEPTH = 32
# Shorter values would hit ordinary words.
_KNOWN_MIN = 8

_known: set[str] = set()
# Longest first, so a secret that contains another one is replaced as a whole.
_known_sorted: tuple[str, ...] = ()
_known_lock = threading.Lock()


def remember_secret(value: str | None) -> None:
    """Register a real secret. Every later mask replaces it wherever it shows up.

    A custom credential is one JSON object; its string values are registered too.
    """
    global _known_sorted
    text = (value or "").strip()
    if not text:
        return
    found = [text]
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if isinstance(data, dict):
            found.extend(_string_leaves(data))
    with _known_lock:
        before = len(_known)
        for item in found:
            cleaned = item.strip()
            if len(cleaned) >= _KNOWN_MIN:
                _known.add(cleaned)
        if len(_known) != before:
            _known_sorted = tuple(sorted(_known, key=len, reverse=True))


def forget_secrets() -> None:
    """Drop every registered secret (tests, vault reset)."""
    global _known_sorted
    with _known_lock:
        _known.clear()
        _known_sorted = ()


def _string_leaves(value: object, depth: int = 0) -> list[str]:
    if depth > 4:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for nested in value.values():
            out.extend(_string_leaves(nested, depth + 1))
        return out
    if isinstance(value, list):
        out = []
        for nested in value:
            out.extend(_string_leaves(nested, depth + 1))
        return out
    return []


def mask_known(value: str) -> str:
    """Replace registered secrets by ``***``. Nothing else changes."""
    secrets = _known_sorted
    if not value or not secrets:
        return value
    masked = value
    for secret in secrets:
        if secret in masked:
            masked = masked.replace(secret, "***")
    return masked


def _mask_key_formats(value: str) -> str:
    masked = _SK_RE.sub("sk-***", value)
    for pattern, replacement in _PROVIDER_KEY_RES:
        masked = pattern.sub(replacement, masked)
    return masked


def mask_text(value: str) -> str:
    """Redact Bearer tokens and known provider key substrings; keep the rest of the string."""
    masked = mask_known(value)
    masked = _BEARER_RE.sub(lambda m: f"{m.group(1)} ***", masked)
    return _mask_key_formats(masked)


def _bearer_token(match: re.Match[str]) -> str:
    token = match.group(3)
    if any(ch.isdigit() for ch in token) and any(ch.isalpha() for ch in token):
        return f"{match.group(1)}{match.group(2)}***"
    return match.group(0)


def mask_content(value: str) -> str:
    """Narrow mask for text a model reads and may write back. See module docstring."""
    masked = mask_known(value)
    masked = _BEARER_TOKEN_RE.sub(_bearer_token, masked)
    return _mask_key_formats(masked)


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


def mask_content_obj(value: object, *, _depth: int = 0) -> object:
    """``mask_obj`` with the narrow string mask. Secret keys still become ``\"***\"``."""
    if _depth >= _CONTENT_MAX_DEPTH:
        return "***"
    if isinstance(value, str):
        return mask_content(value)
    if isinstance(value, dict):
        out: dict[Any, object] = {}
        for key, nested in value.items():
            if _is_secret_key(key):
                out[key] = "***"
            else:
                out[key] = mask_content_obj(nested, _depth=_depth + 1)
        return out
    if isinstance(value, list):
        return [mask_content_obj(item, _depth=_depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_content_obj(item, _depth=_depth + 1) for item in value)
    return value


def _is_secret_key(key: object) -> bool:
    return isinstance(key, str) and key.lower() in _SECRET_KEYS
