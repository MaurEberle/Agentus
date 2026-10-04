"""POST /runtime/ping, GET /runtime/models, POST /runtime/test-llm, GET /runtime/resources."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.common.types import Provider
from app.runtime.catalog import list_openai_compat_models
from app.runtime.completions import test_llm
from app.runtime.errors import RuntimeApiError
from app.runtime.model_stats import get_model_stats
from app.runtime.models import (
    KvLayerOut,
    PingResult,
    RuntimeModelOut,
    RuntimeModelStats,
    RuntimeModelsResponse,
    TestLlmRequest,
)
from app.run.models import ResourceSnapshot
from app.run.resources import latest as latest_resources
from app.runtime.ollama import list_ollama_models, model_block_count, ping_ollama
from app.runtime.vram_est import vram_profile

router = APIRouter()


def _kv_layer_models(profile: object) -> list[KvLayerOut] | None:
    rows = getattr(profile, "kv_layers", None) or ()
    out: list[KvLayerOut] = []
    saw = False
    for layer in rows:
        bpt = int(getattr(layer, "bytes_per_token", 0) or 0)
        window = getattr(layer, "window", None)
        fixed = int(getattr(layer, "fixed_bytes", 0) or 0)
        out.append(
            KvLayerOut(
                bytes_per_token=bpt,
                window=window if isinstance(window, int) and window > 0 else None,
                fixed_bytes=fixed or None,
            )
        )
        if bpt or fixed:
            saw = True
    return out if saw else None


@router.post("/runtime/ping", response_model=PingResult, response_model_exclude_none=True)
def runtime_ping() -> PingResult:
    return ping_ollama()


@router.get("/runtime/models", response_model=RuntimeModelsResponse, response_model_exclude_none=True)
def runtime_models(
    provider: Provider = "ollama",
    credential_id: Annotated[str | None, Query(alias="credentialId")] = None,
    base_url: Annotated[str | None, Query(alias="baseUrl")] = None,
) -> RuntimeModelsResponse:
    try:
        if provider == "ollama":
            models = list_ollama_models(base_url=base_url)
        else:
            models = list_openai_compat_models(
                provider, credential_id=credential_id, base_url=base_url
            )
    except RuntimeApiError as exc:
        if provider == "ollama":
            return RuntimeModelsResponse(items=[])
        return RuntimeModelsResponse(items=[], message_key=exc.error_key)
    return RuntimeModelsResponse(
        items=[RuntimeModelOut(name=item.name, size_bytes=item.size_bytes) for item in models]
    )


@router.get("/runtime/model-stats", response_model=RuntimeModelStats, response_model_exclude_none=True)
def runtime_model_stats(
    model: str,
    provider: Provider = "ollama",
    credential_id: Annotated[str | None, Query(alias="credentialId")] = None,
    base_url: Annotated[str | None, Query(alias="baseUrl")] = None,
) -> RuntimeModelStats:
    tag = model.strip()
    if not tag:
        return RuntimeModelStats()
    try:
        minimum, maximum, steps = get_model_stats(
            provider, tag, credential_id=credential_id, base_url=base_url
        )
    except RuntimeApiError as exc:
        return RuntimeModelStats(message_key=exc.error_key)
    gpu_layers = model_block_count(tag, base_url=base_url) if provider == "ollama" else None
    profile = vram_profile(tag, base_url=base_url) if provider == "ollama" else None
    if profile and profile.layers:
        gpu_layers = profile.layers
    return RuntimeModelStats(
        context_min=minimum,
        context_max=maximum,
        steps=steps,
        gpu_layers=gpu_layers,
        weight_bytes=profile.weight_bytes if profile else None,
        kv_bytes_per_token=profile.kv_bytes_per_token if profile else None,
        kv_swa_bytes_per_token=profile.kv_swa_bytes_per_token if profile else None,
        swa_window=profile.swa_window if profile else None,
        overhead_bytes=profile.overhead_bytes if profile else None,
        kv_layers=_kv_layer_models(profile) if profile else None,
    )


@router.post("/runtime/test-llm", response_model=PingResult, response_model_exclude_none=True)
def runtime_test_llm(body: TestLlmRequest) -> PingResult:
    return test_llm(body)


@router.get("/runtime/resources", response_model=ResourceSnapshot, response_model_exclude_none=True)
def runtime_resources() -> ResourceSnapshot:
    return latest_resources()
