"""Public GGUF search on the Hugging Face Hub. No token, no private repos."""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlencode

from pydantic import Field

from app.common.http import client
from app.http.app import ApiModel
from app.runtime.errors import RuntimeApiError, is_transport_error, raise_for_status, raise_transport, response_json
from app.runtime.ollama import list_ollama_models, tag_key

HUB = "https://huggingface.co"
_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_CACHE_SEC = 60.0
_LIMIT = 30
_REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}/[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
_QUANT = re.compile(
    r"(?i)(?:IQ\d+(?:_[A-Z0-9]+)*|Q\d+(?:_[A-Z0-9]+)*|F16|FP16|BF16|FP8|FP4)"
)
_PULL = re.compile(
    r"^hf\.co/[A-Za-z0-9][A-Za-z0-9._-]{0,80}/[A-Za-z0-9][A-Za-z0-9._-]{0,120}:[A-Za-z0-9][A-Za-z0-9._+-]{0,180}$"
)

PIPELINES = {
    "text": ("text-generation",),
    "embed": ("feature-extraction", "sentence-similarity"),
    "vision": ("image-text-to-text",),
}
SIZES = {
    "any": None,
    "3": "max:3B",
    "8": "min:3B,max:8B",
    "14": "min:8B,max:14B",
    "32": "min:14B,max:32B",
    "70": "min:32B,max:70B",
    "xl": "min:70B",
}
SORTS = {
    "downloads": "downloads",
    "likes": "likes",
    "trending": "trending_score",
    "modified": "last_modified",
}


class HubHit(ApiModel):
    id: str
    pipeline: str | None = None
    downloads: int = 0
    likes: int = 0
    url: str


class HubSearchResponse(ApiModel):
    items: list[HubHit] = Field(default_factory=list)
    message_key: str | None = Field(default=None, alias="messageKey")


class QuantFile(ApiModel):
    quant: str
    filename: str
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    tag: str
    installed: bool = False


class HubFilesResponse(ApiModel):
    id: str
    url: str
    architecture: str | None = None
    context_length: int | None = Field(default=None, alias="contextLength")
    license: str | None = None
    installable: bool = False
    reason: str | None = None
    quants: list[QuantFile] = Field(default_factory=list)
    message_key: str | None = Field(default=None, alias="messageKey")


def valid_repo_id(repo_id: str) -> bool:
    return bool(_REPO_ID.fullmatch((repo_id or "").strip()))


def valid_pull_model(model: str) -> bool:
    return bool(_PULL.fullmatch((model or "").strip()))


def quant_token(filename: str) -> str:
    stem = filename.rsplit("/", 1)[-1]
    if stem.lower().endswith(".gguf"):
        stem = stem[: -len(".gguf")]
    found = _QUANT.findall(stem)
    return found[-1] if found else stem


def keep_hub_row(row: dict[str, Any], pipelines: tuple[str, ...]) -> bool:
    if row.get("private") or row.get("gated"):
        return False
    if row.get("disabled"):
        return False
    tag = row.get("pipeline_tag")
    if pipelines and isinstance(tag, str) and tag not in pipelines:
        return False
    model_id = row.get("modelId") or row.get("id")
    return isinstance(model_id, str) and valid_repo_id(model_id)


def _get_json(url: str) -> Any:
    try:
        with client(timeout_sec=20.0) as http:
            response = http.get(url)
        raise_for_status(response)
        return response_json(response)
    except RuntimeApiError:
        raise
    except Exception as exc:
        if is_transport_error(exc):
            raise_transport(exc)
        raise RuntimeApiError("models.hub.failed") from exc


def _search_one(pipeline: str, *, search: str, size: str | None, sort: str) -> list[dict[str, Any]]:
    params: list[tuple[str, str]] = [
        ("filter", "gguf"),
        ("pipeline_tag", pipeline),
        ("sort", sort),
        ("direction", "-1"),
        ("limit", str(_LIMIT)),
    ]
    if search:
        params.append(("search", search))
    if size:
        params.append(("num_parameters", size))
    url = f"{HUB}/api/models?{urlencode(params)}"
    key = url
    cached = _CACHE.get(key)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_SEC:
        return cached[1]
    payload = _get_json(url)
    rows = payload if isinstance(payload, list) else []
    clean = [row for row in rows if isinstance(row, dict)]
    _CACHE[key] = (now, clean)
    return clean


def search_hub(*, search: str, pipeline: str, size: str, sort: str) -> HubSearchResponse:
    pipes = PIPELINES.get(pipeline, PIPELINES["text"])
    size_query = SIZES.get(size, None)
    sort_key = SORTS.get(sort, "downloads")
    needle = search.strip()[:80]
    try:
        rows: list[dict[str, Any]] = []
        for pipe in pipes:
            rows.extend(_search_one(pipe, search=needle, size=size_query, sort=sort_key))
    except RuntimeApiError as exc:
        return HubSearchResponse(items=[], message_key=exc.error_key)
    seen: set[str] = set()
    items: list[HubHit] = []
    for row in rows:
        if not keep_hub_row(row, pipes):
            continue
        model_id = str(row.get("modelId") or row.get("id"))
        if model_id in seen:
            continue
        seen.add(model_id)
        downloads = row.get("downloads")
        likes = row.get("likes")
        tag = row.get("pipeline_tag")
        items.append(
            HubHit(
                id=model_id,
                pipeline=tag if isinstance(tag, str) else None,
                downloads=int(downloads) if isinstance(downloads, int) else 0,
                likes=int(likes) if isinstance(likes, int) else 0,
                url=f"{HUB}/{model_id}",
            )
        )
        if len(items) >= _LIMIT:
            break
    return HubSearchResponse(items=items)


def _file_size(row: dict[str, Any]) -> int | None:
    lfs = row.get("lfs")
    if isinstance(lfs, dict) and isinstance(lfs.get("size"), int):
        return int(lfs["size"])
    size = row.get("size")
    return int(size) if isinstance(size, int) and size > 0 else None


def _installed_keys() -> set[str]:
    try:
        return {tag_key(item.name) for item in list_ollama_models()}
    except RuntimeApiError:
        return set()


def repo_files(repo_id: str) -> HubFilesResponse:
    repo = repo_id.strip()
    if not valid_repo_id(repo):
        return HubFilesResponse(id=repo, url="", installable=False, reason="invalid", message_key="models.hub.invalid")
    url = f"{HUB}/{repo}"
    try:
        info = _get_json(f"{HUB}/api/models/{repo}")
        tree = _get_json(f"{HUB}/api/models/{repo}/tree/main")
    except RuntimeApiError as exc:
        return HubFilesResponse(id=repo, url=url, installable=False, message_key=exc.error_key)
    if not isinstance(info, dict):
        info = {}
    gated = bool(info.get("gated") or info.get("private"))
    card = info.get("cardData")
    if isinstance(card, dict) and card.get("extra_gated_fields"):
        gated = True
    gguf = info.get("gguf") if isinstance(info.get("gguf"), dict) else {}
    arch = gguf.get("architecture") if isinstance(gguf, dict) else None
    context = gguf.get("context_length") if isinstance(gguf, dict) else None
    license_name = None
    if isinstance(card, dict) and isinstance(card.get("license"), str):
        license_name = card["license"]
    rows = tree if isinstance(tree, list) else []
    files: list[tuple[str, str, int | None]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = row.get("path") or row.get("rfilename")
        if not isinstance(path, str) or not path.lower().endswith(".gguf"):
            continue
        if "mmproj" in path.lower():
            continue
        files.append((path.rsplit("/", 1)[-1], path, _file_size(row)))
    tokens = [quant_token(name) for name, _, _ in files]
    installed = _installed_keys()
    quants: list[QuantFile] = []
    for (filename, _path, size), token in zip(files, tokens, strict=True):
        label = token if tokens.count(token) == 1 else filename
        tag = f"hf.co/{repo}:{label}"
        quants.append(
            QuantFile(
                quant=token,
                filename=filename,
                size_bytes=size,
                tag=tag,
                installed=tag_key(tag) in installed,
            )
        )
    quants.sort(key=lambda item: ((item.quant or "").lower() != "q4_k_m", item.quant.lower()))
    reason = None
    installable = bool(quants) and not gated
    if gated:
        reason = "gated"
        installable = False
    elif not quants:
        reason = "no-gguf"
    return HubFilesResponse(
        id=repo,
        url=url,
        architecture=arch if isinstance(arch, str) else None,
        context_length=int(context) if isinstance(context, int) else None,
        license=license_name,
        installable=installable,
        reason=reason,
        quants=quants,
    )
