"""List models from OpenAI-compatible /v1/models (xAI and openai_compat)."""

from __future__ import annotations

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
from app.runtime.models import OllamaModel
from app.runtime.urls import models_url, settings_roots


def list_openai_compat_models(
    provider: Provider,
    *,
    credential_id: str | None = None,
    secret: str | None = None,
    base_url: str | None = None,
    timeout_sec: float = 8.0,
) -> list[OllamaModel]:
    if provider == "ollama":
        raise RuntimeApiError("runtime.invalidProvider")
    resolved = resolve_secret(secret, credential_id)
    if not resolved:
        raise RuntimeApiError("runtime.missingCredential")
    ollama_root, openai_base = settings_roots()
    url = models_url(
        provider,
        ollama_root=ollama_root,
        override_base=base_url,
        settings_openai=openai_base,
    )
    headers = request_headers(provider, resolved)
    try:
        with client(timeout_sec=timeout_sec) as http:
            response = http.get(url, headers=headers)
        raise_for_status(response)
        payload = response_json(response)
    except RuntimeApiError:
        raise
    except Exception as exc:
        if is_transport_error(exc):
            raise_transport(exc)
        raise
    return [OllamaModel(name=name) for name in _model_names(payload)]


def _model_names(payload: object) -> list[str]:
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            rows = payload["data"]
        elif isinstance(payload.get("models"), list):
            rows = payload["models"]
        else:
            return []
    elif isinstance(payload, list):
        rows = payload
    else:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for item in rows:
        name: str | None = None
        if isinstance(item, str):
            name = item.strip() or None
        elif isinstance(item, dict):
            raw = item.get("id") or item.get("name") or item.get("model")
            if isinstance(raw, str) and raw.strip():
                name = raw.strip()
        if name and name.startswith("models/"):
            name = name[len("models/") :]
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    names.sort()
    return names
