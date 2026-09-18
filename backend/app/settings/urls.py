"""Normalize runtime URLs. Completions add /v1; stored Ollama URL never has it."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def _require_http(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("settings.ollamaUrl.invalid")


def normalize_ollama_base_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        raise ValueError("settings.ollamaUrl.invalid")
    _require_http(raw)
    parsed = urlparse(raw)
    path = parsed.path.rstrip("/")
    if path == "/v1" or path.endswith("/v1"):
        path = path[: -len("/v1")]
    path = path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")).rstrip("/")


def normalize_optional_http_url(url: str | None) -> str | None:
    if url is None:
        return None
    raw = url.strip()
    if not raw:
        return None
    _require_http(raw)
    parsed = urlparse(raw)
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")).rstrip("/")
