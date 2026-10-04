"""Estimate Ollama GPU memory from /api/show plus GGUF size.

Weights scale with offload. The KV cache is reserved for the full num_ctx.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.runtime.ollama import (
    gpu_layers_for_percent,
    list_ollama_models,
    parse_block_count,
    tag_key,
)

_MIB = 1024 * 1024
_ELEM_BYTES = 2  # llama.cpp default KV is f16
_BASE_OVERHEAD = 256 * _MIB
_MOE_OVERHEAD = 256 * _MIB
_LAYER_OVERHEAD = 2 * _MIB


@dataclass(frozen=True)
class VramProfile:
    layers: int | None
    weight_bytes: int | None
    kv_bytes_per_token: int | None
    overhead_bytes: int | None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value > 0:
        return int(value)
    return None


def _arch(info: dict[str, Any]) -> str | None:
    raw = info.get("general.architecture")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    for key in info:
        name = str(key)
        if not name.endswith(".block_count"):
            continue
        stem = name[: -len(".block_count")]
        if stem and "." not in stem:
            return stem
    return None


def _info_int(info: dict[str, Any], arch: str, suffix: str) -> int | None:
    return _positive_int(info.get(f"{arch}.{suffix}"))


def _kv_layers(info: dict[str, Any], arch: str, layers: int) -> int:
    nextn = _info_int(info, arch, "nextn_predict_layers") or 0
    repeating = layers - nextn if nextn and nextn < layers else layers
    interval = _info_int(info, arch, "full_attention_interval")
    if interval and interval > 1:
        return max(1, repeating // interval)
    return max(1, repeating)


def _bytes_per_token_per_layer(info: dict[str, Any], arch: str) -> int | None:
    n_kv = _info_int(info, arch, "attention.head_count_kv")
    k_len = _info_int(info, arch, "attention.key_length")
    v_len = _info_int(info, arch, "attention.value_length")
    lora = _info_int(info, arch, "attention.kv_lora_rank")
    k_mla = _info_int(info, arch, "attention.key_length_mla")
    if lora or k_mla:
        if k_len is None:
            rope = _info_int(info, arch, "rope.dimension_count") or 0
            k_len = (lora or 0) + rope
        if k_len is None:
            return None
        return k_len * (n_kv or 1) * _ELEM_BYTES
    n_head = _info_int(info, arch, "attention.head_count")
    n_embd = _info_int(info, arch, "embedding_length")
    if n_kv is None:
        n_kv = n_head
    if k_len is None and n_embd and n_head:
        k_len = n_embd // n_head
    if k_len is None or n_kv is None:
        return None
    if v_len is None:
        v_len = k_len
    return (k_len + v_len) * n_kv * _ELEM_BYTES


def _overhead_bytes(info: dict[str, Any], arch: str, layers: int | None) -> int:
    overhead = _BASE_OVERHEAD
    experts = _info_int(info, arch, "expert_count")
    if experts and experts > 1:
        overhead += _MOE_OVERHEAD
    if layers:
        overhead += layers * _LAYER_OVERHEAD
    return overhead


def parse_vram_profile(payload: object, size_bytes: int | None) -> VramProfile | None:
    """KV and overhead from ``/api/show``; weights from the GGUF size on disk."""
    if not isinstance(payload, dict):
        return None
    info = payload.get("model_info")
    if not isinstance(info, dict):
        return None
    arch = _arch(info)
    layers = parse_block_count(payload)
    kv_per_token: int | None = None
    overhead: int | None = None
    if arch:
        per_layer = _bytes_per_token_per_layer(info, arch)
        if per_layer and layers:
            kv_per_token = per_layer * _kv_layers(info, arch, layers)
        overhead = _overhead_bytes(info, arch, layers)
    weight = size_bytes if isinstance(size_bytes, int) and size_bytes > 0 else None
    if layers is None and weight is None and kv_per_token is None:
        return None
    return VramProfile(
        layers=layers,
        weight_bytes=weight,
        kv_bytes_per_token=kv_per_token,
        overhead_bytes=overhead,
    )


def estimate_vram_bytes(
    profile: VramProfile,
    *,
    num_ctx: int,
    num_gpu_percent: int,
) -> int:
    """GPU bytes for this context and offload. KV is reserved for the full window."""
    layers = profile.layers
    if layers:
        on = gpu_layers_for_percent(num_gpu_percent, layers)
        frac = on / layers
    else:
        frac = 1.0
    ctx = max(0, int(num_ctx))
    weights = int((profile.weight_bytes or 0) * frac)
    kv = int((profile.kv_bytes_per_token or 0) * ctx * frac)
    overhead = int((profile.overhead_bytes or 0) * frac)
    return weights + kv + overhead


def _size_bytes(tag: str, *, base_url: str | None) -> int | None:
    wanted = tag_key(tag)
    try:
        models = list_ollama_models(base_url=base_url)
    except Exception:
        return None
    for item in models:
        if tag_key(item.name) == wanted and item.size_bytes:
            return item.size_bytes
    return None


def _fetch_show(tag: str, *, base_url: str | None) -> dict[str, Any] | None:
    from app.common.http import client
    from app.runtime.errors import raise_for_status, response_json
    from app.runtime.ollama import _root

    url = f"{_root(base_url)}/api/show"
    try:
        with client(timeout_sec=8.0) as http:
            response = http.post(url, json={"model": tag})
        raise_for_status(response)
        payload = response_json(response)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def vram_profile(tag: str, *, base_url: str | None = None) -> VramProfile | None:
    name = (tag or "").strip()
    if not name:
        return None
    payload = _fetch_show(name, base_url=base_url)
    if payload is None:
        return None
    return parse_vram_profile(payload, _size_bytes(name, base_url=base_url))
