"""Native Ollama: tags, ps, show, generate keep_alive, chat URL via completions."""

from __future__ import annotations

import time
from collections.abc import Iterable
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


_block_counts: dict[str, int] = {}


def _root(base_url: str | None) -> str:
    if base_url:
        return ollama_native_root(base_url)
    return settings_roots()[0]


def _positive_layer(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value > 0:
        return int(value)
    return None


def parse_block_count(payload: object) -> int | None:
    """Transformer layers: ``{architecture}.block_count``, never ``leading_dense_block_count``."""
    if not isinstance(payload, dict):
        return None
    info = payload.get("model_info")
    if not isinstance(info, dict):
        return None
    arch = info.get("general.architecture")
    if isinstance(arch, str) and arch.strip():
        exact = _positive_layer(info.get(f"{arch.strip()}.block_count"))
        if exact:
            return exact
    best: int | None = None
    for key, value in info.items():
        name = str(key)
        if not name.endswith(".block_count"):
            continue
        stem = name[: -len(".block_count")]
        if "." in stem:
            continue
        layer = _positive_layer(value)
        if layer:
            best = layer if best is None else max(best, layer)
    return best


def gpu_layers_for_percent(percent: int, block_count: int | None) -> int:
    """Map 10–100 % offload to Ollama ``num_gpu`` (layer count). Unknown size → 999 (max)."""
    pct = max(10, min(100, int(percent)))
    if not isinstance(block_count, int) or block_count < 1:
        return 999
    if pct >= 100:
        return block_count
    return max(1, min(block_count, (block_count * pct + 50) // 100))


def clamp_gpu_layers(count: int, block_count: int | None) -> int:
    """Keep a layer offload on ``1..block_count``. Unknown size keeps the count."""
    n = max(1, int(count))
    if isinstance(block_count, int) and block_count > 0:
        return min(n, block_count)
    return n


def model_block_count(tag: str, *, base_url: str | None = None) -> int | None:
    name = (tag or "").strip()
    if not name:
        return None
    key = f"{_root(base_url)}|{name}"
    cached = _block_counts.get(key)
    if cached:
        return cached
    url = f"{_root(base_url)}/api/show"
    try:
        with client(timeout_sec=5.0) as http:
            response = http.post(url, json={"model": name})
        raise_for_status(response)
        payload = response_json(response)
    except Exception:
        return None
    count = parse_block_count(payload)
    if count:
        _block_counts[key] = count
    return count


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


def tag_key(name: str) -> str:
    text = (name or "").strip().lower()
    if text.endswith(":latest"):
        text = text[: -len(":latest")]
    return text


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
    wanted = tag_key(tag)
    if any(tag_key(name) == wanted for name in loaded):
        return
    _generate(tag, keep_alive=keep_alive, base_url=base_url)


def unload(tag: str, *, base_url: str | None = None, wait: bool = True) -> None:
    try:
        _generate(tag, keep_alive=0, base_url=base_url)
    except RuntimeApiError as exc:
        if exc.error_key == "runtime.modelNotFound":
            return
        raise
    if wait:
        _wait_absent(tag, base_url=base_url)


def keep_only(keep: Iterable[str], *, base_url: str | None = None) -> list[str]:
    """Unload every resident model that is not in ``keep``. Returns dropped tags."""
    keep_keys = {tag_key(item) for item in keep if str(item).strip()}
    dropped: list[str] = []
    try:
        loaded = list_loaded_models(base_url=base_url)
    except Exception:
        return dropped
    for name in loaded:
        if tag_key(name) in keep_keys:
            continue
        try:
            unload(name, base_url=base_url)
        except Exception:
            continue
        dropped.append(name)
    return dropped


def _wait_absent(tag: str, *, base_url: str | None, timeout_sec: float = 20.0) -> None:
    wanted = tag_key(tag)
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            names = list_loaded_models(base_url=base_url)
        except Exception:
            return
        if all(tag_key(name) != wanted for name in names):
            return
        time.sleep(0.25)


def _generate(
    tag: str, *, keep_alive: str | int, base_url: str | None, timeout_sec: float = 180.0
) -> None:
    url = f"{_root(base_url)}/api/generate"
    body: dict[str, Any] = {"model": tag, "prompt": "", "keep_alive": keep_alive}
    try:
        with client(timeout_sec=timeout_sec) as http:
            response = http.post(url, json=body)
    except Exception as exc:
        if is_transport_error(exc):
            raise_transport(exc)
        raise
    raise_for_status(response)
