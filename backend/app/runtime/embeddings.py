"""OpenAI-compatible embeddings. Caller passes model; this module does not pick one."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.common.http import client
from app.runtime.completions import _auth_secret, _endpoint, request_headers
from app.runtime.errors import (
    RuntimeApiError,
    is_transport_error,
    raise_for_status,
    raise_transport,
    response_json,
)
from app.runtime.models import EmbedRequest, EmbedResult

# Cloud embedding APIs reject a whole corpus in one body (Gemini batches top out
# near 100 inputs; OpenAI also caps tokens per request). Keep each call small.
_BATCH = 64
_progress: Callable[[int, int], None] | None = None


@contextmanager
def progress_hook(fn: Callable[[int, int], None] | None) -> Iterator[None]:
    global _progress
    previous = _progress
    _progress = fn
    try:
        yield
    finally:
        _progress = previous


def _notify_progress(done: int, total: int) -> None:
    hook = _progress
    if hook is not None:
        hook(done, total)


def embed(req: EmbedRequest) -> EmbedResult:
    if not req.texts:
        return EmbedResult(vectors=[], dimension=0, model=req.model)
    try:
        return _embed_batched(req)
    except RuntimeApiError as exc:
        # Ollama only passes --embedding when the GGUF has pooling_type.
        # Qwen-VL embedding models still embed if llama-server is started that way.
        if (
            exc.error_key == "runtime.embedUnsupported"
            and req.provider == "ollama"
            and not req.base_url
        ):
            from app.runtime.ollama_embed_runner import embed_with_forced_runner

            return embed_with_forced_runner(req)
        raise


def _embed_batched(req: EmbedRequest, *, batch_size: int | None = None) -> EmbedResult:
    size = batch_size or _BATCH
    total = len(req.texts)
    if total <= size:
        out = _embed_once(req)
        _notify_progress(total, total)
        return out
    vectors: list[list[float]] = []
    dimension = 0
    for start in range(0, total, size):
        batch = req.texts[start : start + size]
        part = _embed_once(req.model_copy(update={"texts": batch}))
        if vectors and part.dimension != dimension:
            raise RuntimeApiError("runtime.badRequest")
        dimension = part.dimension
        vectors.extend(part.vectors)
        _notify_progress(len(vectors), total)
    return EmbedResult(vectors=vectors, dimension=dimension, model=req.model)


def _vector(raw: object) -> list[float]:
    if isinstance(raw, dict):
        raw = raw.get("values")
    if not isinstance(raw, list):
        raise RuntimeApiError("runtime.badRequest")
    return [float(item) for item in raw]


def _embed_once(req: EmbedRequest) -> EmbedResult:
    secret = _auth_secret(req.provider, req.secret, req.credential_id)
    url = _endpoint(req.provider, req.base_url, embeddings=True)
    headers = request_headers(req.provider, secret)
    try:
        with client(timeout_sec=req.timeout_sec) as http:
            response = http.post(
                url,
                json={"model": req.model, "input": req.texts},
                headers=headers,
            )
        if response.status_code == 501:
            raise RuntimeApiError("runtime.embedUnsupported", status=501)
        raise_for_status(response)
        body = response_json(response)
    except RuntimeApiError:
        raise
    except Exception as exc:
        if is_transport_error(exc):
            raise_transport(exc)
        raise
    if not isinstance(body, dict):
        raise RuntimeApiError("runtime.badRequest")
    rows = body.get("data")
    if not isinstance(rows, list):
        raise RuntimeApiError("runtime.badRequest")
    ordered = sorted(
        (row for row in rows if isinstance(row, dict)),
        key=lambda row: int(row.get("index") or 0),
    )
    vectors = [_vector(row.get("embedding")) for row in ordered]
    if len(vectors) != len(req.texts):
        raise RuntimeApiError("runtime.badRequest")
    dimension = len(vectors[0]) if vectors else 0
    return EmbedResult(vectors=vectors, dimension=dimension, model=req.model)
