"""Estimate Ollama GPU memory from /api/show plus GGUF size.

Weights scale with offload fraction. KV is summed per layer. Ollama places
GPU layers from the end of the block list (last N). Full-attention KV uses
the whole num_ctx; sliding-window layers only their window. Recurrent/SSM
state does not grow with context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.runtime.ollama import (
    clamp_gpu_layers,
    gpu_layers_for_percent,
    list_ollama_models,
    ollama_num_gpu,
    parse_block_count,
    tag_key,
)

_MIB = 1024 * 1024
_ELEM_BYTES = 2  # llama.cpp default KV is f16
_SSM_ELEM_BYTES = 4  # recurrent cache is f32
_BASE_OVERHEAD = 256 * _MIB
_MOE_OVERHEAD = 256 * _MIB
_LAYER_OVERHEAD = 2 * _MIB

_SWA_MARKERS = ("sliding", "local", "swa", "chunk")
_RECURRENT_MARKERS = ("linear", "mamba", "delta", "recurrent", "conv", "ssm")
_SKIP_MARKERS = ("mlp", "ffn", "moe", "dense", "none", "noop")


@dataclass(frozen=True)
class LayerKv:
    """One transformer block's cache. Empty fields mean the block has no KV."""

    bytes_per_token: int = 0
    window: int | None = None
    fixed_bytes: int = 0


@dataclass(frozen=True)
class VramProfile:
    layers: int | None
    weight_bytes: int | None
    kv_bytes_per_token: int | None
    overhead_bytes: int | None
    kv_swa_bytes_per_token: int | None = None
    swa_window: int | None = None
    kv_layers: tuple[LayerKv, ...] = ()
    expert_count: int | None = None
    expert_used_count: int | None = None
    routed_expert_bytes: int | None = None
    non_expert_bytes: int | None = None
    leading_dense_blocks: int | None = None
    expert_layers: int | None = None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value > 0:
        return int(value)
    return None


def _is_list(value: object) -> bool:
    return isinstance(value, list) and len(value) > 0


def _layer_int(value: object, index: int) -> int | None:
    """Scalar or cycling per-layer list. 0 is real (no KV on that layer)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value >= 0:
        return int(value)
    if isinstance(value, (list, tuple)) and value:
        item = value[index % len(value)]
        if isinstance(item, bool) or item is None:
            return None
        if isinstance(item, int) and item >= 0:
            return item
        if isinstance(item, float) and item >= 0:
            return int(item)
    return None


def _bool_pattern(value: object, n: int) -> list[bool] | None:
    if n < 1 or not isinstance(value, list) or not value:
        return None
    flags: list[bool] = []
    for item in value:
        if isinstance(item, bool):
            flags.append(item)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            flags.append(int(item) != 0)
        else:
            return None
    if not flags:
        return None
    return [flags[i % len(flags)] for i in range(n)]


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


def _info_get(info: dict[str, Any], arch: str, suffix: str) -> object:
    return info.get(f"{arch}.{suffix}")


def _info_int(info: dict[str, Any], arch: str, suffix: str) -> int | None:
    return _positive_int(_info_get(info, arch, suffix))


def _kv_end(info: dict[str, Any], arch: str, layers: int) -> int:
    end = layers
    nextn = _info_int(info, arch, "nextn_predict_layers") or 0
    if nextn and nextn < end:
        end -= nextn
    shared = _info_int(info, arch, "attention.shared_kv_layers") or 0
    if shared and shared < end:
        end -= shared
    return max(0, end)


def _layer_types(info: dict[str, Any], arch: str, n: int) -> list[str] | None:
    raw = _info_get(info, arch, "attention.layer_types")
    if isinstance(raw, str) and raw.strip():
        return [raw.strip().lower()] * n
    if not isinstance(raw, (list, tuple)) or not raw:
        return None
    out: list[str] = []
    for i in range(n):
        item = raw[i % len(raw)]
        out.append(str(item).strip().lower() if item is not None else "")
    return out


def _kind_from_type(label: str) -> str:
    text = label.replace("-", "_")
    if any(marker in text for marker in _SWA_MARKERS):
        return "swa"
    if any(marker in text for marker in _RECURRENT_MARKERS):
        return "recurrent"
    if any(marker in text for marker in _SKIP_MARKERS):
        return "skip"
    return "full"


def _classify_layer(
    *,
    index: int,
    kv_end: int,
    types: list[str] | None,
    n_kv_raw: object,
    n_head_raw: object,
    pattern: list[bool] | None,
    arch: str,
    window: int | None,
    interval: int | None,
    interval_is_recurrent: bool,
    mla: bool,
) -> str:
    if index >= kv_end:
        return "skip"
    if types is not None:
        kind = _kind_from_type(types[index])
    else:
        n_kv = _layer_int(n_kv_raw, index)
        n_head = _layer_int(n_head_raw, index)
        if n_kv == 0 or n_head == 0:
            return "recurrent"
        if pattern is not None:
            kind = "swa" if pattern[index] else "full"
        elif arch in {"gemma3", "gemma3n"} and window:
            kind = "swa" if (index + 1) % 6 != 0 else "full"
        elif interval and interval > 1:
            # Qwen3.5-style hybrids: the other layers are DeltaNet, not empty.
            kind = "full" if index % interval == 0 else ("recurrent" if interval_is_recurrent else "skip")
        elif window and not mla:
            kind = "swa"
        else:
            kind = "full"
    if kind == "full":
        n_kv = _layer_int(n_kv_raw, index)
        n_head = _layer_int(n_head_raw, index)
        if n_kv == 0 or n_head == 0:
            return "recurrent"
    return kind


def _gqa_bytes(
    info: dict[str, Any],
    arch: str,
    index: int,
    *,
    swa: bool,
    n_kv_raw: object,
    n_head_raw: object,
) -> int | None:
    n_kv = _layer_int(n_kv_raw, index)
    n_head = _layer_int(n_head_raw, index)
    if n_kv is None:
        n_kv = n_head
    if n_kv is None or n_kv <= 0:
        return None
    if swa:
        k_len = _layer_int(_info_get(info, arch, "attention.key_length_swa"), index)
        v_len = _layer_int(_info_get(info, arch, "attention.value_length_swa"), index)
        if k_len is None or k_len <= 0:
            k_len = _layer_int(_info_get(info, arch, "attention.key_length"), index)
        if v_len is None or v_len <= 0:
            v_len = _layer_int(_info_get(info, arch, "attention.value_length"), index)
    else:
        k_len = _layer_int(_info_get(info, arch, "attention.key_length"), index)
        v_len = _layer_int(_info_get(info, arch, "attention.value_length"), index)
    if k_len is None or k_len <= 0:
        n_embd = _info_int(info, arch, "embedding_length")
        if n_embd and n_head:
            k_len = n_embd // n_head
    if k_len is None or k_len <= 0:
        return None
    if v_len is None or v_len <= 0:
        v_len = k_len
    return (k_len + v_len) * n_kv * _ELEM_BYTES


def _mla_bytes(
    info: dict[str, Any],
    arch: str,
    index: int,
    *,
    n_kv_raw: object,
    lora: int | None,
) -> int | None:
    n_kv = _layer_int(n_kv_raw, index)
    if n_kv is None:
        n_kv = 1
    if n_kv <= 0:
        return None
    k_len = _layer_int(_info_get(info, arch, "attention.key_length"), index)
    if k_len is None or k_len <= 0:
        rope = _info_int(info, arch, "rope.dimension_count") or 0
        k_len = (lora or 0) + rope
    if k_len is None or k_len <= 0:
        k_len = _layer_int(_info_get(info, arch, "attention.key_length_mla"), index)
    if k_len is None or k_len <= 0:
        return None
    return k_len * n_kv * _ELEM_BYTES


def _recurrent_bytes(info: dict[str, Any], arch: str) -> int:
    conv = _info_int(info, arch, "ssm.conv_kernel") or 0
    state = _info_int(info, arch, "ssm.state_size") or 0
    inner = _info_int(info, arch, "ssm.inner_size") or 0
    groups = _info_int(info, arch, "ssm.group_count") or 0
    n_r = (conv - 1) * (inner + 2 * groups * state) if conv > 0 else 0
    n_s = state * inner
    return (n_r + n_s) * _SSM_ELEM_BYTES


def _build_kv_layers(info: dict[str, Any], arch: str, layers: int) -> tuple[LayerKv, ...]:
    n_kv_raw = _info_get(info, arch, "attention.head_count_kv")
    n_head_raw = _info_get(info, arch, "attention.head_count")
    pattern = _bool_pattern(_info_get(info, arch, "attention.sliding_window_pattern"), layers)
    window_raw = _info_get(info, arch, "attention.sliding_window")
    window = _layer_int(window_raw, 0) if _is_list(window_raw) else _positive_int(window_raw)
    interval = _info_int(info, arch, "full_attention_interval")
    lora = _info_int(info, arch, "attention.kv_lora_rank")
    k_mla = _info_int(info, arch, "attention.key_length_mla")
    mla = bool(lora or k_mla)
    types = _layer_types(info, arch, layers)
    kv_end = _kv_end(info, arch, layers)
    items: list[LayerKv] = []
    for i in range(layers):
        kind = _classify_layer(
            index=i,
            kv_end=kv_end,
            types=types,
            n_kv_raw=n_kv_raw,
            n_head_raw=n_head_raw,
            pattern=pattern,
            arch=arch,
            window=window,
            interval=interval,
            interval_is_recurrent=bool(_info_int(info, arch, "ssm.inner_size")),
            mla=mla,
        )
        if kind == "skip":
            items.append(LayerKv())
            continue
        if kind == "recurrent":
            items.append(LayerKv(fixed_bytes=_recurrent_bytes(info, arch)))
            continue
        if kind == "swa":
            bpt = _gqa_bytes(info, arch, i, swa=True, n_kv_raw=n_kv_raw, n_head_raw=n_head_raw)
            layer_window = _layer_int(window_raw, i) if _is_list(window_raw) else window
            items.append(
                LayerKv(
                    bytes_per_token=bpt or 0,
                    window=layer_window if layer_window and layer_window > 0 else None,
                )
            )
            continue
        bpt = (
            _mla_bytes(info, arch, i, n_kv_raw=n_kv_raw, lora=lora)
            if mla
            else _gqa_bytes(info, arch, i, swa=False, n_kv_raw=n_kv_raw, n_head_raw=n_head_raw)
        )
        items.append(LayerKv(bytes_per_token=bpt or 0))
    return tuple(items)


def _aggregates(layers: tuple[LayerKv, ...]) -> tuple[int | None, int | None, int | None]:
    full = 0
    swa = 0
    windows: list[int] = []
    for layer in layers:
        if layer.bytes_per_token <= 0:
            continue
        if layer.window and layer.window > 0:
            swa += layer.bytes_per_token
            windows.append(layer.window)
        else:
            full += layer.bytes_per_token
    return (full or None, swa or None, max(windows) if windows else None)


def _sum_kv(layers: tuple[LayerKv, ...], num_ctx: int, on: int) -> int:
    if not layers or on <= 0:
        return 0
    ctx = max(0, int(num_ctx))
    start = max(0, len(layers) - min(on, len(layers)))
    total = 0
    for layer in layers[start:]:
        total += layer.fixed_bytes
        if layer.bytes_per_token <= 0:
            continue
        tokens = min(ctx, layer.window) if layer.window and layer.window > 0 else ctx
        total += layer.bytes_per_token * tokens
    return total


def _clamp_leading(leading: int | None, layers: int) -> int:
    n = leading or 0
    if n < 0:
        return 0
    if n > layers:
        return layers
    return n


def _attention_params(info: dict[str, Any], arch: str, n_embd: int) -> int:
    """Q, K, V and output projection. Missing head metadata falls back to a square block."""
    n_head = _info_int(info, arch, "attention.head_count")
    n_kv = _info_int(info, arch, "attention.head_count_kv") or n_head
    key = _info_int(info, arch, "attention.key_length")
    value = _info_int(info, arch, "attention.value_length") or key
    if n_head and n_kv and key and value:
        return (
            n_embd * n_head * key
            + n_embd * n_kv * key
            + n_embd * n_kv * value
            + n_head * value * n_embd
        )
    return 4 * n_embd * n_embd


def _moe_weight_split(
    info: dict[str, Any], arch: str, layers: int | None, size_bytes: int | None
) -> tuple[int, int | None, int, int, int, int] | None:
    """Split the GGUF size into routed-expert bytes and everything else.

    The ratio uses parameter counts from ``/api/show``. Shared experts and the
    leading dense blocks stay on the non-expert side. ``expert_used_count`` is
    not part of the size.
    """
    experts = _info_int(info, arch, "expert_count")
    expert_ffn = _info_int(info, arch, "expert_feed_forward_length")
    # Llama-arch merges publish expert_count but keep the FFN width on
    # feed_forward_length. Without that fallback the file is estimated as dense.
    if not expert_ffn:
        expert_ffn = _info_int(info, arch, "feed_forward_length")
    n_embd = _info_int(info, arch, "embedding_length")
    if (
        not experts
        or experts <= 1
        or not expert_ffn
        or not n_embd
        or not layers
        or not isinstance(size_bytes, int)
        or size_bytes <= 0
    ):
        return None
    leading = _clamp_leading(_info_int(info, arch, "leading_dense_block_count"), layers)
    expert_layers = layers - leading
    if expert_layers < 1:
        return None
    routed_params = experts * 3 * n_embd * expert_ffn * expert_layers
    shared_count = _info_int(info, arch, "expert_shared_count") or 0
    shared_ffn = _info_int(info, arch, "expert_shared_feed_forward_length")
    if shared_count and not shared_ffn:
        shared_ffn = _info_int(info, arch, "feed_forward_length") or expert_ffn
    shared_params = (
        shared_count * 3 * n_embd * shared_ffn * expert_layers if shared_count and shared_ffn else 0
    )
    dense_ffn = _info_int(info, arch, "feed_forward_length") or 0
    dense_params = 3 * n_embd * dense_ffn * leading if dense_ffn and leading else 0
    other_params = _attention_params(info, arch, n_embd) * layers + shared_params + dense_params
    total_params = routed_params + other_params
    if total_params <= 0 or routed_params <= 0:
        return None
    routed_bytes = size_bytes * routed_params // total_params
    # MXFP4 experts sit near 4.5 bits. A uniform parameter split gives those
    # bytes to the experts and starves the denser attention and embedding
    # tensors. The measured Qwen3.6 load kept 2.4 GiB of dense weights on GPU.
    expert_cap = routed_params * 9 // 16
    # Only when experts stay the majority. A synthetic file that is far
    # heavier than its expert params keeps the uniform split.
    if 0 < expert_cap < routed_bytes and expert_cap > size_bytes - expert_cap:
        routed_bytes = expert_cap
    non_expert_bytes = size_bytes - routed_bytes
    used = _info_int(info, arch, "expert_used_count")
    return experts, used, routed_bytes, non_expert_bytes, leading, expert_layers


def _overhead_bytes(info: dict[str, Any], arch: str, layers: int | None) -> int:
    overhead = _BASE_OVERHEAD
    experts = _info_int(info, arch, "expert_count")
    if experts and experts > 1:
        overhead += _MOE_OVERHEAD
    if layers:
        overhead += layers * _LAYER_OVERHEAD
    return overhead


def _offload_on(layers: int | None, num_gpu: int | None, num_gpu_percent: int | None) -> tuple[int, float]:
    if not layers:
        return 0, 1.0
    if isinstance(num_gpu, int) and num_gpu > 0:
        on = clamp_gpu_layers(num_gpu, layers)
    elif isinstance(num_gpu_percent, int) and num_gpu_percent > 0:
        on = gpu_layers_for_percent(num_gpu_percent, layers)
    else:
        on = layers
    return on, on / layers


def parse_vram_profile(payload: object, size_bytes: int | None) -> VramProfile | None:
    """KV and overhead from ``/api/show``; weights from the GGUF size on disk."""
    if not isinstance(payload, dict):
        return None
    info = payload.get("model_info")
    if not isinstance(info, dict):
        return None
    arch = _arch(info)
    layers = parse_block_count(payload)
    kv_layers: tuple[LayerKv, ...] = ()
    kv_per_token: int | None = None
    kv_swa: int | None = None
    swa_window: int | None = None
    overhead: int | None = None
    if arch:
        if layers:
            kv_layers = _build_kv_layers(info, arch, layers)
            kv_per_token, kv_swa, swa_window = _aggregates(kv_layers)
        overhead = _overhead_bytes(info, arch, layers)
    weight = size_bytes if isinstance(size_bytes, int) and size_bytes > 0 else None
    split = _moe_weight_split(info, arch, layers, weight) if arch else None
    if layers is None and weight is None and kv_per_token is None and kv_swa is None and split is None:
        return None
    return VramProfile(
        layers=layers,
        weight_bytes=weight,
        kv_bytes_per_token=kv_per_token,
        overhead_bytes=overhead,
        kv_swa_bytes_per_token=kv_swa,
        swa_window=swa_window,
        kv_layers=kv_layers,
        expert_count=split[0] if split else (_info_int(info, arch, "expert_count") if arch else None),
        expert_used_count=(
            split[1] if split else (_info_int(info, arch, "expert_used_count") if arch else None)
        ),
        routed_expert_bytes=split[2] if split else None,
        non_expert_bytes=split[3] if split else None,
        leading_dense_blocks=split[4] if split else None,
        expert_layers=split[5] if split else None,
    )


def kv_bytes_for_ctx(profile: VramProfile, num_ctx: int) -> int:
    if profile.kv_layers:
        return _sum_kv(profile.kv_layers, num_ctx, len(profile.kv_layers))
    ctx = max(0, int(num_ctx))
    full = (profile.kv_bytes_per_token or 0) * ctx
    swa_pt = profile.kv_swa_bytes_per_token or 0
    window = profile.swa_window or 0
    if swa_pt <= 0:
        swa = 0
    elif window > 0:
        swa = swa_pt * min(ctx, window)
    else:
        swa = swa_pt * ctx
    return full + swa


def estimate_vram_bytes(
    profile: VramProfile,
    *,
    num_ctx: int,
    num_gpu: int | None = None,
    num_gpu_percent: int | None = None,
) -> int:
    """GPU bytes for this context and offload. Last N layers hold KV on the GPU."""
    on, frac = _offload_on(profile.layers, num_gpu, num_gpu_percent)
    weights = int((profile.weight_bytes or 0) * frac)
    if profile.kv_layers:
        kv = _sum_kv(profile.kv_layers, num_ctx, on if profile.layers else len(profile.kv_layers))
    else:
        kv = int(kv_bytes_for_ctx(profile, num_ctx) * frac)
    overhead = int((profile.overhead_bytes or 0) * frac)
    return weights + kv + overhead


@dataclass(frozen=True)
class MoeFit:
    """Automatic placement: attention first, then as many whole expert layers as fit."""

    gpu_bytes: int
    ram_bytes: int
    experts_on_gpu: int
    expert_layers: int
    attention_layers_on_gpu: int
    non_expert_on_gpu: int
    expert_on_gpu_bytes: int
    kv_bytes: int
    overhead_bytes: int


def _fixed_gpu(profile: VramProfile, num_ctx: int, on: int, layers: int) -> tuple[int, int, int]:
    non_expert = int((profile.non_expert_bytes or 0) * on // layers)
    overhead = int((profile.overhead_bytes or 0) * on // layers)
    if profile.kv_layers:
        kv = _sum_kv(profile.kv_layers, num_ctx, on)
    else:
        kv = int(kv_bytes_for_ctx(profile, num_ctx) * on // layers) if layers else 0
    return non_expert, kv, overhead


# llama.cpp leaves this much free VRAM and reserves a flat compute buffer.
# The Qwen3.6 load used 5.22 GiB against a 7.49 GiB fill-the-card estimate.
_FIT_MARGIN = 1024 * 1024 * 1024
_COMPUTE_RESERVE = 256 * 1024 * 1024


def fit_moe(profile: VramProfile, *, num_ctx: int, pool_bytes: int) -> MoeFit | None:
    """How many routed expert layers fit beside the dense tensors and KV.

    llama.cpp keeps every dense tensor on the GPU, then adds whole expert
    layers and, when it fits, the up and gate matrices of one more layer.
    The down matrix of that layer stays in RAM. A 1 GiB margin and the
    compute buffer are reserved before those layers are counted.
    """
    layers = profile.layers or 0
    routed = profile.routed_expert_bytes or 0
    non_expert = profile.non_expert_bytes or 0
    if layers < 1 or routed <= 0 or non_expert <= 0 or pool_bytes <= 0:
        return None
    leading = _clamp_leading(profile.leading_dense_blocks, layers)
    expert_layers = profile.expert_layers or (layers - leading)
    if expert_layers < 1:
        return None
    budget = pool_bytes - _FIT_MARGIN - _COMPUTE_RESERVE
    if budget <= 0:
        return MoeFit(
            gpu_bytes=0,
            ram_bytes=non_expert + routed,
            experts_on_gpu=0,
            expert_layers=expert_layers,
            attention_layers_on_gpu=0,
            non_expert_on_gpu=0,
            expert_on_gpu_bytes=0,
            kv_bytes=0,
            overhead_bytes=0,
        )
    on = layers
    while on > 0:
        weights, kv, _overhead = _fixed_gpu(profile, num_ctx, on, layers)
        if weights + kv <= budget:
            break
        on -= 1
    weights, kv, _overhead = _fixed_gpu(profile, num_ctx, on, layers)
    room = max(0, budget - (weights + kv))
    cap = min(on, expert_layers)
    per_layer = routed // expert_layers if expert_layers else 0
    experts_on = min(cap, room // per_layer) if per_layer and cap > 0 else 0
    expert_on_gpu = per_layer * experts_on
    # Up and gate are about two thirds of an expert layer. The down matrix stays in RAM.
    partial = (2 * per_layer) // 3
    if experts_on < cap and partial > 0 and room - expert_on_gpu >= partial:
        expert_on_gpu += partial
    non_total = profile.non_expert_bytes or 0
    ram_bytes = max(0, non_total - weights) + max(0, routed - expert_on_gpu)
    return MoeFit(
        gpu_bytes=weights + kv + _COMPUTE_RESERVE + expert_on_gpu,
        ram_bytes=ram_bytes,
        experts_on_gpu=experts_on,
        expert_layers=expert_layers,
        attention_layers_on_gpu=on,
        non_expert_on_gpu=weights,
        expert_on_gpu_bytes=expert_on_gpu,
        kv_bytes=kv,
        overhead_bytes=_COMPUTE_RESERVE,
    )


@dataclass(frozen=True)
class MoeOffload:
    """Expert-layer split the run can send, plus the GPU bytes that split implies."""

    num_gpu: int
    num_cpu_moe: int
    estimated_gpu_bytes: int
    ram_bytes: int
    experts_on_gpu: int
    expert_layers: int
    attention_layers_on_gpu: int


def plan_moe_offload(
    profile: VramProfile | None, *, num_ctx: int, pool_bytes: int
) -> MoeOffload | None:
    """Map a fit onto ``num_gpu`` and ``num_cpu_moe``.

    ``num_cpu_moe`` is the leading block count whose expert tensors stay in RAM:
    dense prefix plus every expert layer that does not fit. ``num_gpu`` is the
    llama.cpp offload of the attention layers that fit, including the output slot.
    """
    if profile is None:
        return None
    fit = fit_moe(profile, num_ctx=num_ctx, pool_bytes=pool_bytes)
    if fit is None:
        return None
    layers = profile.layers or 0
    cpu_experts = max(0, fit.expert_layers - fit.experts_on_gpu)
    leading = profile.leading_dense_blocks or 0
    return MoeOffload(
        num_gpu=ollama_num_gpu(fit.attention_layers_on_gpu, layers if layers else None),
        num_cpu_moe=(leading + cpu_experts) if cpu_experts else 0,
        estimated_gpu_bytes=fit.gpu_bytes,
        ram_bytes=fit.ram_bytes,
        experts_on_gpu=fit.experts_on_gpu,
        expert_layers=fit.expert_layers,
        attention_layers_on_gpu=fit.attention_layers_on_gpu,
    )


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
