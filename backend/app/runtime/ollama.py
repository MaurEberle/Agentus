"""Native Ollama: tags, ps, generate keep_alive. Not /api/chat."""

from __future__ import annotations

from typing import Any

from app.common.http import client
from app.runtime.errors import (
    RuntimeApiError,
    is_transport_error,
    raise_for_status,
    raise_transport,
    response_json,
)
from app.runtime.models import OllamaModel, PingResult
from app.runtime.urls import ollama_native_root, settings_roots


def _root(base_url: str | None) -> str:
    if base_url:
        return ollama_native_root(base_url)
    return settings_roots()[0]


def ping_ollama(*, base_url: str | None = None, timeout_sec: float = 3.0) -> PingResult:
    url = f"{_root(base_url)}/api/tags"
    try:
        with client(timeout_sec=timeout_sec) as http:
            response = http.get(url)
    except Exception:
        return PingResult(ok=False, message_key="runtime.unreachable")
    if response.status_code != 200:
        from app.runtime.errors import map_http_status

        return PingResult(ok=False, message_key=map_http_status(response.status_code))
    return PingResult(ok=True)


def list_ollama_models(*, base_url: str | None = None) -> list[OllamaModel]:
    url = f"{_root(base_url)}/api/tags"
    try:
        with client(timeout_sec=5.0) as http:
            response = http.get(url)
        raise_for_status(response)
        payload = response_json(response)
    except RuntimeApiError:
        raise
    except Exception as exc:
        raise_transport(exc)
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    out: list[OllamaModel] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if not isinstance(name, str) or not name:
            continue
        size = item.get("size")
        size_bytes = int(size) if isinstance(size, int) else None
        out.append(OllamaModel(name=name, size_bytes=size_bytes))
    return out


def list_loaded_models(*, base_url: str | None = None) -> list[str]:
    url = f"{_root(base_url)}/api/ps"
    try:
        with client(timeout_sec=5.0) as http:
            response = http.get(url)
        raise_for_status(response)
        payload = response_json(response)
    except RuntimeApiError:
        raise
    except Exception as exc:
        raise_transport(exc)
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    names: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def ensure_loaded(
    tag: str, *, base_url: str | None = None, keep_alive: str = "5m"
) -> None:
    loaded = list_loaded_models(base_url=base_url)
    if tag in loaded:
        return
    _generate(tag, keep_alive=keep_alive, base_url=base_url)


def unload(tag: str, *, base_url: str | None = None) -> None:
    try:
        _generate(tag, keep_alive=0, base_url=base_url)
    except RuntimeApiError as exc:
        if exc.error_key == "runtime.modelNotFound":
            return
        raise


def _generate(
    tag: str, *, keep_alive: str | int, base_url: str | None
) -> None:
    url = f"{_root(base_url)}/api/generate"
    body: dict[str, Any] = {"model": tag, "prompt": "", "keep_alive": keep_alive}
    try:
        with client(timeout_sec=30.0) as http:
            response = http.post(url, json=body)
    except Exception as exc:
        if is_transport_error(exc):
            raise_transport(exc)
        raise
    raise_for_status(response)
