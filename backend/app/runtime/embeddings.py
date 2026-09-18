"""OpenAI-compatible embeddings. Caller passes model; this module does not pick one."""

from __future__ import annotations

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


def embed(req: EmbedRequest) -> EmbedResult:
    if not req.texts:
        return EmbedResult(vectors=[], dimension=0, model=req.model)
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
    vectors: list[list[float]] = []
    for row in ordered:
        embedding = row.get("embedding")
        if not isinstance(embedding, list):
            raise RuntimeApiError("runtime.badRequest")
        vectors.append([float(x) for x in embedding])
    if len(vectors) != len(req.texts):
        raise RuntimeApiError("runtime.badRequest")
    dimension = len(vectors[0]) if vectors else 0
    return EmbedResult(vectors=vectors, dimension=dimension, model=req.model)
