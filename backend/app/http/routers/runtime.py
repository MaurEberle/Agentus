"""POST /runtime/ping, GET /runtime/models, POST /runtime/test-llm. Always HTTP 200."""

from __future__ import annotations

from fastapi import APIRouter

from app.runtime.errors import RuntimeApiError
from app.runtime.models import PingResult, RuntimeModelOut, RuntimeModelsResponse, TestLlmRequest
from app.runtime.ollama import list_ollama_models, ping_ollama
from app.runtime.completions import test_llm

router = APIRouter()


@router.post("/runtime/ping", response_model=PingResult, response_model_exclude_none=True)
def runtime_ping() -> PingResult:
    return ping_ollama()


@router.get("/runtime/models", response_model=RuntimeModelsResponse)
def runtime_models() -> RuntimeModelsResponse:
    try:
        models = list_ollama_models()
    except RuntimeApiError:
        return RuntimeModelsResponse(items=[])
    return RuntimeModelsResponse(
        items=[RuntimeModelOut(name=item.name, size_bytes=item.size_bytes) for item in models]
    )


@router.post("/runtime/test-llm", response_model=PingResult, response_model_exclude_none=True)
def runtime_test_llm(body: TestLlmRequest) -> PingResult:
    return test_llm(body)
