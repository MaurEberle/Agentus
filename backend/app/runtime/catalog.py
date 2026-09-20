"""List models from OpenAI-compatible /v1/models (and Gemini native /v1beta/models)."""

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

GEMINI_NATIVE_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


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
    compat_names: list[str] = []
    compat_error: RuntimeApiError | None = None
    try:
        with client(timeout_sec=timeout_sec) as http:
            response = http.get(url, headers=headers)
        raise_for_status(response)
        compat_names = _model_names(response_json(response))
    except RuntimeApiError as exc:
        compat_error = exc
    except Exception as exc:
        if is_transport_error(exc):
            raise_transport(exc)
        raise
    native_names: list[str] = []
    if provider == "gemini":
        try:
            native_names = _list_gemini_native(resolved, timeout_sec=timeout_sec)
        except RuntimeApiError:
            if not compat_names:
                if compat_error:
                    raise compat_error
                raise
    names = sorted(set(compat_names) | set(native_names))
    if not names and compat_error:
        raise compat_error
    return [OllamaModel(name=name) for name in names]


def _list_gemini_native(secret: str, *, timeout_sec: float) -> list[str]:
    headers = {
        "Authorization": f"Bearer {secret}",
        "x-goog-api-key": secret,
    }
    names: list[str] = []
    page_token: str | None = None
    for _ in range(5):
        params: dict[str, str] = {"pageSize": "200"}
        if page_token:
            params["pageToken"] = page_token
        try:
            with client(timeout_sec=timeout_sec) as http:
                response = http.get(GEMINI_NATIVE_MODELS_URL, headers=headers, params=params)
            raise_for_status(response)
            payload = response_json(response)
        except RuntimeApiError:
            raise
        except Exception as exc:
            if is_transport_error(exc):
                raise_transport(exc)
            raise
        names.extend(_model_names(payload))
        if not isinstance(payload, dict):
            break
        token = payload.get("nextPageToken")
        if not isinstance(token, str) or not token:
            break
        page_token = token
    return names


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
