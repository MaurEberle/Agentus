"""Describe installed Ollama models for the Modelle module."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.db.model_tags import all_model_tags
from app.http.app import ApiModel
from app.runtime.errors import RuntimeApiError
from app.runtime.ollama import (
    _expert_count,
    cached_show,
    list_ollama_models,
    parse_block_count,
    resident_index,
    tag_key,
)

_LICENSE_CAP = 4000
class InstalledModel(ApiModel):
    name: str
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    digest: str | None = None
    modified_at: str | None = Field(default=None, alias="modifiedAt")
    family: str | None = None
    parameter_size: str | None = Field(default=None, alias="parameterSize")
    quantization: str | None = None
    format: str | None = None
    architecture: str | None = None
    context_length: int | None = Field(default=None, alias="contextLength")
    embedding_length: int | None = Field(default=None, alias="embeddingLength")
    block_count: int | None = Field(default=None, alias="blockCount")
    expert_count: int | None = Field(default=None, alias="expertCount")
    capabilities: list[str] = Field(default_factory=list)
    kind: str = "normal"
    vision: bool = False
    tools: bool = False
    thinking: bool = False
    has_template: bool = Field(default=False, alias="hasTemplate")
    license: str | None = None
    license_clipped: bool = Field(default=False, alias="licenseClipped")
    hf_url: str | None = Field(default=None, alias="hfUrl")
    loaded: bool = False
    vram_bytes: int | None = Field(default=None, alias="vramBytes")
    tags: list[str] = Field(default_factory=list)


class InstalledResponse(ApiModel):
    items: list[InstalledModel] = Field(default_factory=list)
    message_key: str | None = Field(default=None, alias="messageKey")


def huggingface_url(name: str) -> str | None:
    text = (name or "").strip()
    lowered = text.lower()
    prefix = ""
    for candidate in ("hf.co/", "huggingface.co/"):
        if lowered.startswith(candidate):
            prefix = candidate
            break
    if not prefix:
        return None
    rest = text[len(prefix) :].split(":", 1)[0].strip("/")
    if rest.count("/") != 1 or ".." in rest.split("/"):
        return None
    owner, repo = rest.split("/", 1)
    if not owner or not repo:
        return None
    return f"https://huggingface.co/{owner}/{repo}"


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _positive(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value > 0:
        return int(value)
    return None


def _capabilities(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("capabilities")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip().lower())
    return out


def _license(payload: dict[str, Any]) -> tuple[str | None, bool]:
    raw = payload.get("license")
    if isinstance(raw, list):
        text = "\n".join(str(item) for item in raw if str(item).strip())
    elif isinstance(raw, str):
        text = raw
    else:
        return None, False
    text = text.strip()
    if not text:
        return None, False
    if len(text) <= _LICENSE_CAP:
        return text, False
    return text[:_LICENSE_CAP], True


def _named_embedding(name: str) -> bool:
    return "embed" in (name or "").lower()


def _ollama_embedding(capabilities: list[str], info: dict[str, Any]) -> bool:
    """Capability list or the GGUF pooling type Ollama uses for embedders."""
    if "embedding" in capabilities:
        return True
    for key, value in info.items():
        if not str(key).endswith(".pooling_type"):
            continue
        if value is None or value == "":
            continue
        return True
    return False


def is_embedding(name: str, capabilities: list[str], info: dict[str, Any] | None = None) -> bool:
    """Name and Ollama data together.

    An ``embedding`` capability or a pooling type is enough. A name that says
    embedder counts when Ollama did not mark the model as an image generator.
    Chat models also have an embedding length, so that field alone does not count.
    """
    meta = info or {}
    caps = [item.lower() for item in capabilities]
    if _ollama_embedding(caps, meta):
        return True
    if not _named_embedding(name):
        return False
    return "image" not in caps


def model_kind(
    name: str,
    capabilities: list[str],
    *,
    moe: bool,
    info: dict[str, Any] | None = None,
) -> str:
    if is_embedding(name, capabilities, info):
        return "embedding"
    caps = set(capabilities)
    if "image" in caps:
        return "image"
    if moe:
        return "moe"
    return "normal"


def describe_show(name: str, payload: dict[str, Any] | None, *, moe: bool) -> dict[str, Any]:
    details = payload.get("details") if isinstance(payload, dict) else None
    info = payload.get("model_info") if isinstance(payload, dict) else None
    details = details if isinstance(details, dict) else {}
    info = info if isinstance(info, dict) else {}
    caps = _capabilities(payload) if isinstance(payload, dict) else []
    if is_embedding(name, caps, info) and "embedding" not in caps:
        caps = ["embedding", *caps]
    arch = _text(info.get("general.architecture"))
    context = _positive(info.get(f"{arch}.context_length")) if arch else None
    embedding = _positive(info.get(f"{arch}.embedding_length")) if arch else None
    experts = _expert_count(payload) if isinstance(payload, dict) else None
    license_text, clipped = _license(payload) if isinstance(payload, dict) else (None, False)
    template = payload.get("template") if isinstance(payload, dict) else None
    return {
        "family": _text(details.get("family")),
        "parameter_size": _text(details.get("parameter_size")),
        "quantization": _text(details.get("quantization_level")),
        "format": _text(details.get("format")),
        "architecture": arch,
        "context_length": context,
        "embedding_length": embedding,
        "block_count": parse_block_count(payload) if isinstance(payload, dict) else None,
        "expert_count": experts if experts and experts > 1 else None,
        "capabilities": caps,
        "kind": model_kind(name, caps, moe=moe, info=info),
        "vision": "vision" in caps,
        "tools": "tools" in caps,
        "thinking": "thinking" in caps,
        "has_template": isinstance(template, str) and bool(template.strip()),
        "license": license_text,
        "license_clipped": clipped,
    }


def list_installed() -> InstalledResponse:
    try:
        models = list_ollama_models()
    except RuntimeApiError as exc:
        return InstalledResponse(items=[], message_key=exc.error_key)
    resident = resident_index()
    stored = all_model_tags()
    items: list[InstalledModel] = []
    for model in models:
        shown = describe_show(model.name, cached_show(model.name), moe=model.moe)
        size, vram = resident.get(tag_key(model.name), (None, None))
        items.append(
            InstalledModel(
                name=model.name,
                size_bytes=model.size_bytes if model.size_bytes is not None else size,
                digest=model.digest,
                modified_at=model.modified_at,
                hf_url=huggingface_url(model.name),
                loaded=tag_key(model.name) in resident,
                vram_bytes=vram,
                tags=stored.get(tag_key(model.name), []),
                **shown,
            )
        )
    items.sort(key=lambda item: item.name.lower())
    return InstalledResponse(items=items)
