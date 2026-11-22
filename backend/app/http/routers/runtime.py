"""POST /runtime/ping, GET /runtime/models, POST /runtime/test-llm, GET /runtime/resources.

GET /runtime/ollama, POST /runtime/ollama/check and POST /runtime/ollama/update
report and update Agentus' own Ollama copy.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.common.types import Provider
from app.http.app import ApiModel
from app.http.errors import AppError
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
from app.runtime.ollama_own import (
    OwnOllamaStatus,
    OwnRuntimeError,
    build_status,
    download_running,
    get_own,
)
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


class OllamaUpdateResult(ApiModel):
    version: str
    restart: bool


@router.get("/runtime/ollama", response_model=OwnOllamaStatus)
def runtime_ollama() -> OwnOllamaStatus:
    return build_status()


@router.post("/runtime/ollama/check", response_model=OwnOllamaStatus)
def runtime_ollama_check() -> OwnOllamaStatus:
    own = get_own()
    if own.mode == "own":
        own.check_update()
    return build_status()


@router.post("/runtime/ollama/update", response_model=OllamaUpdateResult)
def runtime_ollama_update() -> OllamaUpdateResult:
    """Take over the installed Ollama version, then restart Agentus (desktop window)."""
    from app.host.restart import request_restart
    from app.settings.service import is_run_busy

    try:
        version = get_own().apply_update(run_busy=is_run_busy(), download_running=download_running())
    except OwnRuntimeError as exc:
        raise AppError(exc.key, status_code=exc.status_code) from None
    return OllamaUpdateResult(version=version, restart=request_restart())


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
        items=[
            RuntimeModelOut(
                name=item.name,
                size_bytes=item.size_bytes,
                moe=item.moe,
                parameter_size=item.parameter_size,
                quantization=item.quantization,
            )
            for item in models
        ]
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
        expert_count=getattr(profile, "expert_count", None) if profile else None,
        expert_used_count=getattr(profile, "expert_used_count", None) if profile else None,
        routed_expert_bytes=getattr(profile, "routed_expert_bytes", None) if profile else None,
        non_expert_bytes=getattr(profile, "non_expert_bytes", None) if profile else None,
        leading_dense_blocks=getattr(profile, "leading_dense_blocks", None) if profile else None,
        projector_bytes=(getattr(profile, "projector_bytes", 0) or None) if profile else None,
    )


@router.post("/runtime/test-llm", response_model=PingResult, response_model_exclude_none=True)
def runtime_test_llm(body: TestLlmRequest) -> PingResult:
    return test_llm(body)


@router.get("/runtime/resources", response_model=ResourceSnapshot, response_model_exclude_none=True)
def runtime_resources() -> ResourceSnapshot:
    return latest_resources()
