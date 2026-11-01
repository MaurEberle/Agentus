"""Public GGUF search on the Hugging Face Hub. No token, no private repos."""

from __future__ import annotations

import base64
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from pydantic import Field

from app.common.http import client
from app.http.app import ApiModel
from app.runtime.errors import RuntimeApiError, is_transport_error, raise_for_status, raise_transport, response_json
from app.runtime.ollama import list_ollama_models, tag_key

HUB = "https://huggingface.co"
_CACHE: dict[str, tuple[float, tuple[list[dict[str, Any]], str | None]]] = {}
_CACHE_SEC = 60.0
_FLAG_CACHE: dict[str, tuple[float, tuple[bool, bool, bool]]] = {}
_FLAG_SEC = 600.0
_PAGE_SIZES = (10, 20, 30, 50, 100)
_DEFAULT_PAGE_SIZE = 30
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')
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
_BOUND = re.compile(r"^\d+(?:\.\d+)?$")


def parameter_query(size: str) -> str | None:
    """Preset key or ``min:0.6B,max:4B``. Anything else is ignored."""
    if size in SIZES:
        return SIZES[size]
    parts = [part.strip() for part in size.split(",") if part.strip()]
    if not parts or len(parts) > 2:
        return None
    minimum: str | None = None
    maximum: str | None = None
    for part in parts:
        kind, _, raw = part.partition(":")
        if not raw.endswith("B") or not _BOUND.fullmatch(raw[:-1]):
            return None
        if kind == "min" and minimum is None:
            minimum = f"min:{raw}"
        elif kind == "max" and maximum is None:
            maximum = f"max:{raw}"
        else:
            return None
    ordered = [item for item in (minimum, maximum) if item]
    return ",".join(ordered) or None


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
    tools: bool = False
    thinking: bool = False
    vision: bool = False


class HubSearchResponse(ApiModel):
    items: list[HubHit] = Field(default_factory=list)
    page_size: int = Field(default=_DEFAULT_PAGE_SIZE, alias="pageSize")
    has_next: bool = Field(default=False, alias="hasNext")
    next_cursor: str | None = Field(default=None, alias="nextCursor")
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
    author: str | None = None
    pipeline: str | None = None
    downloads: int = 0
    likes: int = 0
    updated_at: str | None = Field(default=None, alias="updatedAt")
    repo_bytes: int | None = Field(default=None, alias="repoBytes")
    architecture: str | None = None
    context_length: int | None = Field(default=None, alias="contextLength")
    license: str | None = None
    license_url: str | None = Field(default=None, alias="licenseUrl")
    base_model: str | None = Field(default=None, alias="baseModel")
    base_url: str | None = Field(default=None, alias="baseUrl")
    languages: list[str] = Field(default_factory=list)
    has_template: bool = Field(default=False, alias="hasTemplate")
    tools: bool = False
    thinking: bool = False
    vision: bool = False
    installable: bool = False
    reason: str | None = None
    quants: list[QuantFile] = Field(default_factory=list)
    message_key: str | None = Field(default=None, alias="messageKey")


def valid_repo_id(repo_id: str) -> bool:
    return bool(_REPO_ID.fullmatch((repo_id or "").strip()))


def valid_pull_model(model: str) -> bool:
    return bool(_PULL.fullmatch((model or "").strip()))


def keep_weight_file(path: str) -> bool:
    """A weight file Ollama can pull. Imatrix and vision projectors are not models."""
    name = (path or "").lower()
    if not name.endswith(".gguf"):
        return False
    return "mmproj" not in name and "imatrix" not in name


def flags_from_card(info: dict[str, Any]) -> tuple[bool, bool, bool]:
    """Tools, thinking, and vision. Same rules as the detail pane."""
    gguf = info.get("gguf") if isinstance(info.get("gguf"), dict) else {}
    template = gguf.get("chat_template") if isinstance(gguf, dict) else ""
    tags = info.get("tags") if isinstance(info.get("tags"), list) else []
    tools, thinking = template_flags(
        template if isinstance(template, str) else "",
        [str(item) for item in tags],
    )
    pipeline = info.get("pipeline_tag")
    vision = pipeline == "image-text-to-text"
    return tools, thinking, vision


def model_flags(model_id: str) -> tuple[bool, bool, bool]:
    cached = _FLAG_CACHE.get(model_id)
    now = time.monotonic()
    if cached and now - cached[0] < _FLAG_SEC:
        return cached[1]
    try:
        info = _get_json(f"{HUB}/api/models/{model_id}")
    except RuntimeApiError:
        return False, False, False
    flags = flags_from_card(info if isinstance(info, dict) else {})
    _FLAG_CACHE[model_id] = (now, flags)
    return flags


def template_flags(template: str, tags: list[str]) -> tuple[bool, bool]:
    """Tool calling and thinking from the GGUF chat template and Hub tags."""
    text = (template or "").lower()
    tools = "tool_call" in text or "tool_calls" in text
    tag_set = {item.lower() for item in tags if isinstance(item, str)}
    thinking = "<think" in text or bool(tag_set & {"reasoning", "thinking", "efficient-thinking"})
    return tools, thinking


def page_limit(value: int) -> int:
    """Snap to 10, 20, 30, 50, or 100."""
    if value in _PAGE_SIZES:
        return value
    return min(_PAGE_SIZES, key=lambda mark: (abs(mark - value), mark))


def cursor_from_link(header: str | None) -> str | None:
    if not header:
        return None
    found = _NEXT_LINK.search(header)
    if not found:
        return None
    values = parse_qs(urlparse(found.group(1)).query).get("cursor") or []
    cursor = values[0] if values else ""
    if not cursor or len(cursor) > 4000:
        return None
    return cursor


def pack_cursors(cursors: list[str | None]) -> str | None:
    if all(item is None for item in cursors):
        return None
    if len(cursors) == 1:
        return cursors[0]
    raw = base64.urlsafe_b64encode(json.dumps(cursors).encode()).decode().rstrip("=")
    return f"v1.{raw}"


def unpack_cursors(token: str | None, count: int) -> list[str | None] | None:
    """None starts every pipeline at the first page. A list skips exhausted ones."""
    if not token:
        return None
    if count == 1 and not token.startswith("v1."):
        return [token]
    if not token.startswith("v1."):
        return None
    padded = token[3:] + "=" * (-len(token[3:]) % 4)
    try:
        loaded = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, list) or len(loaded) != count:
        return None
    out: list[str | None] = []
    for item in loaded:
        if item is None or (isinstance(item, str) and len(item) <= 4000):
            out.append(item if isinstance(item, str) else None)
        else:
            return None
    return out


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


def _search_one(
    pipeline: str,
    *,
    search: str,
    size: str | None,
    sort: str,
    limit: int,
    cursor: str | None,
    direction: str = "-1",
) -> tuple[list[dict[str, Any]], str | None]:
    params: list[tuple[str, str]] = [
        ("filter", "gguf"),
        ("pipeline_tag", pipeline),
        ("sort", sort),
        ("direction", "-1"),
        ("limit", str(limit)),
    ]
    if search:
        params.append(("search", search))
    if size:
        params.append(("num_parameters", size))
    if cursor:
        params.append(("cursor", cursor))
    url = f"{HUB}/api/models?{urlencode(params)}"
    cached = _CACHE.get(url)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_SEC:
        return cached[1]
    try:
        with client(timeout_sec=20.0) as http:
            response = http.get(url)
        raise_for_status(response)
        payload = response_json(response)
    except RuntimeApiError:
        raise
    except Exception as exc:
        if is_transport_error(exc):
            raise_transport(exc)
        raise RuntimeApiError("models.hub.failed") from exc
    rows = payload if isinstance(payload, list) else []
    clean = [row for row in rows if isinstance(row, dict)]
    nxt = cursor_from_link(response.headers.get("link"))
    _CACHE[url] = (now, (clean, nxt))
    return clean, nxt


_CAPABILITIES = ("tools", "thinking", "vision")
_SCAN_PAGES = 8


def parse_capabilities(raw: str) -> tuple[str, ...]:
    found: list[str] = []
    for part in (raw or "").split(","):
        key = part.strip().lower()
        if key in _CAPABILITIES and key not in found:
            found.append(key)
    return tuple(found)


def _matches(item: HubHit, wanted: tuple[str, ...]) -> bool:
    return all(getattr(item, key) for key in wanted)


def _row_hit(row: dict[str, Any]) -> HubHit | None:
    model_id = row.get("modelId") or row.get("id")
    if not isinstance(model_id, str):
        return None
    downloads = row.get("downloads")
    likes = row.get("likes")
    tag = row.get("pipeline_tag")
    return HubHit(
        id=model_id,
        pipeline=tag if isinstance(tag, str) else None,
        downloads=int(downloads) if isinstance(downloads, int) else 0,
        likes=int(likes) if isinstance(likes, int) else 0,
        url=f"{HUB}/{model_id}",
    )


def _pack_scan(states: list[dict[str, Any]]) -> str | None:
    if all(state.get("done") for state in states):
        return None
    raw = base64.urlsafe_b64encode(json.dumps(states).encode()).decode().rstrip("=")
    return f"f1.{raw}"


def _unpack_scan(token: str | None, count: int) -> list[dict[str, Any]] | None:
    if not token:
        return None
    if not token.startswith("f1."):
        return None
    padded = token[3:] + "=" * (-len(token[3:]) % 4)
    try:
        loaded = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, list) or len(loaded) != count:
        return None
    states: list[dict[str, Any]] = []
    for item in loaded:
        if not isinstance(item, dict):
            return None
        skip = item.get("skip")
        if skip is None:
            skip = []
        if not isinstance(skip, list) or any(not isinstance(name, str) for name in skip):
            return None
        hf = item.get("hf")
        if hf is not None and not isinstance(hf, str):
            return None
        states.append({"hf": hf, "skip": skip, "done": bool(item.get("done"))})
    return states


def _search_capable(
    *,
    pipes: tuple[str, ...],
    needle: str,
    size_query: str | None,
    sort_key: str,
    page: int,
    cursor: str | None,
    wanted: tuple[str, ...],
    direction: str,
) -> HubSearchResponse:
    """Keep reading Hub pages until the page is full of models with the chosen capabilities."""
    states = _unpack_scan(cursor, len(pipes))
    if states is None:
        states = [{"hf": None, "skip": [], "done": False} for _ in pipes]
    collected: list[HubHit] = []
    seen: set[str] = set()
    scanned = 0
    try:
        while len(collected) < page and scanned < _SCAN_PAGES:
            moved = False
            for index, pipe in enumerate(pipes):
                state = states[index]
                if state.get("done") or len(collected) >= page:
                    continue
                rows, nxt = _search_one(
                    pipe,
                    search=needle,
                    size=size_query,
                    sort=sort_key,
                    limit=page,
                    cursor=state.get("hf") if isinstance(state.get("hf"), str) else None,
                    direction=direction,
                )
                scanned += 1
                hits = [hit for row in rows if (hit := _row_hit(row)) and keep_hub_row(row, pipes)]
                _attach_flags(hits)
                skip = {name for name in state.get("skip", []) if isinstance(name, str)}
                pending = False
                taken = list(skip)
                for hit in hits:
                    if hit.id in skip or hit.id in seen:
                        continue
                    if not _matches(hit, wanted):
                        continue
                    if len(collected) >= page:
                        pending = True
                        break
                    collected.append(hit)
                    seen.add(hit.id)
                    taken.append(hit.id)
                if pending:
                    states[index] = {"hf": state.get("hf"), "skip": taken, "done": False}
                    break
                if nxt:
                    states[index] = {"hf": nxt, "skip": [], "done": False}
                    moved = True
                else:
                    states[index] = {"hf": None, "skip": [], "done": True}
                if scanned >= _SCAN_PAGES:
                    break
            if len(collected) >= page or not moved and all(item.get("done") for item in states):
                break
            if not moved:
                break
    except RuntimeApiError as exc:
        return HubSearchResponse(items=[], page_size=page, message_key=exc.error_key)
    collected.sort(key=lambda item: item.downloads, reverse=True)
    if direction == "1":
        collected.reverse()
    nxt_token = _pack_scan(states)
    return HubSearchResponse(
        items=collected[:page],
        page_size=page,
        has_next=nxt_token is not None,
        next_cursor=nxt_token,
    )


def search_hub(
    *,
    search: str,
    pipeline: str,
    size: str,
    sort: str,
    limit: int = _DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
    capabilities: str = "",
    direction: str = "desc",
) -> HubSearchResponse:
    pipes = PIPELINES.get(pipeline, PIPELINES["text"])
    size_query = parameter_query(size)
    sort_key = SORTS.get(sort, "downloads")
    page = page_limit(limit)
    needle = search.strip()[:80]
    order = "1" if direction == "asc" else "-1"
    wanted = parse_capabilities(capabilities)
    if wanted:
        return _search_capable(
            pipes=pipes,
            needle=needle,
            size_query=size_query,
            sort_key=sort_key,
            page=page,
            cursor=cursor,
            wanted=wanted,
            direction=order,
        )
    incoming = unpack_cursors(cursor, len(pipes))
    try:
        batches: list[list[dict[str, Any]]] = []
        following: list[str | None] = []
        for index, pipe in enumerate(pipes):
            pipe_cursor = None if incoming is None else incoming[index]
            if incoming is not None and pipe_cursor is None:
                batches.append([])
                following.append(None)
                continue
            rows, nxt = _search_one(
                pipe,
                search=needle,
                size=size_query,
                sort=sort_key,
                limit=page,
                cursor=pipe_cursor,
                direction=order,
            )
            batches.append(rows)
            following.append(nxt)
    except RuntimeApiError as exc:
        return HubSearchResponse(items=[], page_size=page, message_key=exc.error_key)
    seen: set[str] = set()
    items: list[HubHit] = []
    for row in (row for batch in batches for row in batch):
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
        if len(items) >= page:
            break
    _attach_flags(items)
    if order == "1":
        items.reverse()
    nxt = pack_cursors(following)
    return HubSearchResponse(items=items, page_size=page, has_next=nxt is not None, next_cursor=nxt)


def _attach_flags(items: list[HubHit]) -> None:
    if not items:
        return
    with ThreadPoolExecutor(max_workers=min(8, len(items))) as pool:
        flags = list(pool.map(lambda item: model_flags(item.id), items))
    for item, (tools, thinking, vision) in zip(items, flags, strict=True):
        item.tools = tools
        item.thinking = thinking
        item.vision = vision


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
    template = gguf.get("chat_template") if isinstance(gguf, dict) else ""
    template = template if isinstance(template, str) else ""
    tags = info.get("tags") if isinstance(info.get("tags"), list) else []
    tools, thinking = template_flags(template, [str(item) for item in tags])
    license_name = None
    license_url = None
    languages: list[str] = []
    base_model = None
    if isinstance(card, dict):
        raw_license = card.get("license_name") or card.get("license")
        if isinstance(raw_license, str) and raw_license.strip():
            license_name = raw_license.strip()
        if isinstance(card.get("license_link"), str):
            license_url = card["license_link"]
        raw_lang = card.get("language")
        if isinstance(raw_lang, str) and raw_lang.strip():
            languages = [raw_lang.strip()]
        elif isinstance(raw_lang, list):
            languages = [str(item) for item in raw_lang if str(item).strip()]
        raw_base = card.get("base_model")
        if isinstance(raw_base, list) and raw_base:
            raw_base = raw_base[0]
        if isinstance(raw_base, str) and raw_base.strip() and valid_repo_id(raw_base.strip()):
            base_model = raw_base.strip()
    pipeline = info.get("pipeline_tag") if isinstance(info.get("pipeline_tag"), str) else None
    author = info.get("author") if isinstance(info.get("author"), str) else None
    updated = info.get("lastModified") if isinstance(info.get("lastModified"), str) else None
    downloads = info.get("downloads")
    likes = info.get("likes")
    storage = info.get("usedStorage")
    rows = tree if isinstance(tree, list) else []
    files: list[tuple[str, str, int | None]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = row.get("path") or row.get("rfilename")
        if not isinstance(path, str) or not keep_weight_file(path):
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
        author=author,
        pipeline=pipeline,
        downloads=int(downloads) if isinstance(downloads, int) else 0,
        likes=int(likes) if isinstance(likes, int) else 0,
        updated_at=updated,
        repo_bytes=int(storage) if isinstance(storage, int) and storage > 0 else None,
        architecture=arch if isinstance(arch, str) else None,
        context_length=int(context) if isinstance(context, int) else None,
        license=license_name,
        license_url=license_url,
        base_model=base_model,
        base_url=f"{HUB}/{base_model}" if base_model else None,
        languages=languages,
        has_template=bool(template.strip()),
        tools=tools,
        thinking=thinking,
        vision=pipeline == "image-text-to-text",
        installable=installable,
        reason=reason,
        quants=quants,
    )
