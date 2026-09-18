"""Join inference URLs once. Never emit /v1/v1."""

from __future__ import annotations

from app.common.types import PROVIDERS, Provider
from app.runtime.errors import RuntimeApiError
from app.settings.defaults import DEFAULT_OLLAMA_BASE_URL
from app.settings.urls import normalize_ollama_base_url

DEFAULT_XAI_BASE = "https://api.x.ai/v1"


def ollama_native_root(settings_base: str | None) -> str:
    raw = (settings_base or "").strip() or DEFAULT_OLLAMA_BASE_URL
    try:
        return normalize_ollama_base_url(raw)
    except ValueError:
        return DEFAULT_OLLAMA_BASE_URL


def _join_api(base: str, suffix: str) -> str:
    root = base.rstrip("/")
    path = suffix.lstrip("/")
    if root.endswith("/v1"):
        return f"{root}/{path}"
    return f"{root}/v1/{path}"


def _provider_base(
    provider: Provider,
    *,
    ollama_root: str,
    override_base: str | None,
    settings_openai: str | None,
) -> str:
    if provider not in PROVIDERS:
        raise RuntimeApiError("runtime.invalidProvider")
    if provider == "ollama":
        return (override_base or ollama_root).rstrip("/")
    if provider == "xai":
        return (override_base or DEFAULT_XAI_BASE).rstrip("/")
    base = (override_base or settings_openai or "").strip()
    if not base:
        raise RuntimeApiError("runtime.missingBaseUrl")
    return base.rstrip("/")


def completions_url(
    provider: Provider,
    *,
    ollama_root: str,
    override_base: str | None,
    settings_openai: str | None,
) -> str:
    return _join_api(
        _provider_base(
            provider,
            ollama_root=ollama_root,
            override_base=override_base,
            settings_openai=settings_openai,
        ),
        "chat/completions",
    )


def embeddings_url(
    provider: Provider,
    *,
    ollama_root: str,
    override_base: str | None,
    settings_openai: str | None,
) -> str:
    return _join_api(
        _provider_base(
            provider,
            ollama_root=ollama_root,
            override_base=override_base,
            settings_openai=settings_openai,
        ),
        "embeddings",
    )


def settings_roots() -> tuple[str, str | None]:
    """``(ollama_root, openai_compat_base_url_or_none)`` from settings, with defaults."""
    try:
        from app.settings.service import load_settings

        settings = load_settings()
        return ollama_native_root(settings.ollama_base_url), settings.openai_compat_base_url
    except Exception:
        return ollama_native_root(None), None
