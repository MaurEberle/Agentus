"""Public GGUF search on the Hugging Face Hub. No token, no private repos."""

from __future__ import annotations

import base64
import json
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from pydantic import Field

from app.common.http import client
from app.http.app import ApiModel
from app.runtime.errors import (
    RuntimeApiError,
    is_transport_error,
    raise_for_status,
    raise_transport,
    response_json,
    retry_after_seconds,
)
from app.runtime.ollama import list_ollama_models, tag_key

HUB = "https://huggingface.co"
_CACHE: dict[str, tuple[float, tuple[list[dict[str, Any]], str | None]]] = {}
_CACHE_SEC = 60.0
_CACHE_MAX = 200
_CACHE_LOCK = threading.Lock()
_HUB_TIMEOUT = 12.0  # one Hub call
_SEARCH_SECONDS = 25.0  # what one search may spend reading the Hub
# Without a token the Hub allows 500 calls in 5 minutes ("ratelimit-policy" header). After a 429
# nothing is sent until the window resets, or every call would only stretch the block.
_COOLDOWN = {"until": 0.0}
_COOLDOWN_MAX = 300.0
_RATELIMIT_RESET = re.compile(r"[;,]\s*t=(\d+)")
# Asked with every search page, so sorting, filtering and the tools/thinking/MoE marks need no
# call per model. The chat template is read once and dropped (``slim_row``).
_EXPAND = (
    "downloads",
    "likes",
    "pipeline_tag",
    "tags",
    "gguf",
    "trendingScore",
    "lastModified",
    "private",
    "gated",
    "disabled",
)
_ROW_KEEP = (
    "id",
    "modelId",
    "pipeline_tag",
    "downloads",
    "likes",
    "trendingScore",
    "lastModified",
    "private",
    "gated",
    "disabled",
)
_HUB_ERRORS = {
    "runtime.timeout": "models.hub.timeout",
    "runtime.unreachable": "models.hub.unreachable",
    "runtime.rateLimited": "models.hub.rateLimited",
}
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


def type_selection(pipeline: str) -> tuple[str, bool]:
    """Task keys, and whether MoE further restricts them. MoE alone means every task."""
    keys = [part.strip() for part in (pipeline or "").split(",") if part.strip() and part.strip() != "all"]
    moe = "moe" in keys
    tasks = [key for key in keys if key in PIPELINES]
    return ",".join(tasks), moe


def pipeline_tags(pipeline: str) -> tuple[str, ...]:
    """UI keys, comma-separated. Empty or ``all`` means every type."""
    keys = [part.strip() for part in pipeline.split(",") if part.strip() and part.strip() != "all" and part.strip() != "moe"]
    if not keys:
        keys = ["text", "embed", "vision"]
    tags: list[str] = []
    seen: set[str] = set()
    for key in keys:
        for tag in PIPELINES.get(key, ()):
            if tag not in seen:
                seen.add(tag)
                tags.append(tag)
    return tuple(tags) if tags else PIPELINES["text"]
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
_MOE_NAME = re.compile(
    r"(?i)(?:^|[^a-z0-9])moe(?:[^a-z0-9]|$)"
    r"|\d+x\d+(?:\.\d+)?b"
    r"|(?:^|[-_])a\d+(?:\.\d+)?b(?:[^a-z0-9]|$)"
    r"|mixtral"
)
_DEEPSEEK_MOE = re.compile(r"(?i)deepseek[-_ ]?v[234]")


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
    "trending": "trendingScore",
    "modified": "lastModified",
}


def hf_sort_key(sort: str) -> str:
    """Hub names. The Hub sorts these four, and only descending; anything else is downloads."""
    return SORTS.get(sort, "downloads")


def sort_value(row: dict[str, Any], sort_key: str) -> float | str:
    """The value the Hub sorted a row by, so rows of several tasks merge in the same order."""
    value = row.get(sort_key)
    if sort_key == "lastModified":
        return value if isinstance(value, str) else ""
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


class HubHit(ApiModel):
    id: str
    pipeline: str | None = None
    downloads: int = 0
    likes: int = 0
    url: str
    tools: bool = False
    thinking: bool = False
    vision: bool = False
    moe: bool = False


class HubSearchResponse(ApiModel):
    items: list[HubHit] = Field(default_factory=list)
    page_size: int = Field(default=_DEFAULT_PAGE_SIZE, alias="pageSize")
    has_next: bool = Field(default=False, alias="hasNext")
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    message_key: str | None = Field(default=None, alias="messageKey")
    # Seconds until the Hub takes calls again, with models.hub.rateLimited.
    retry_after: int | None = Field(default=None, alias="retryAfter")


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
    parameters: str | None = None
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
    moe: bool = False
    installable: bool = False
    reason: str | None = None
    quants: list[QuantFile] = Field(default_factory=list)
    message_key: str | None = Field(default=None, alias="messageKey")
    retry_after: int | None = Field(default=None, alias="retryAfter")


def valid_repo_id(repo_id: str) -> bool:
    return bool(_REPO_ID.fullmatch((repo_id or "").strip()))


def valid_pull_model(model: str) -> bool:
    return bool(_PULL.fullmatch((model or "").strip()))


def format_parameter_count(count: int) -> str | None:
    """27B, 1.72B, 596M. The same scale the installed list shows."""
    if count <= 0:
        return None
    if count >= 1_000_000_000:
        scaled, suffix = count / 1_000_000_000, "B"
    elif count >= 1_000_000:
        scaled, suffix = count / 1_000_000, "M"
    elif count >= 1_000:
        scaled, suffix = count / 1_000, "K"
    else:
        return str(count)
    if scaled >= 100:
        text = str(round(scaled))
    elif scaled >= 10:
        text = f"{scaled:.1f}".rstrip("0").rstrip(".")
    else:
        text = f"{scaled:.2f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


def parameter_label(info: dict[str, Any]) -> str | None:
    gguf = info.get("gguf") if isinstance(info.get("gguf"), dict) else {}
    total = gguf.get("total") if isinstance(gguf, dict) else None
    if not isinstance(total, int) or total <= 0:
        safe = info.get("safetensors") if isinstance(info.get("safetensors"), dict) else {}
        total = safe.get("total") if isinstance(safe, dict) else None
    if isinstance(total, int):
        return format_parameter_count(total)
    return None


def keep_weight_file(path: str) -> bool:
    """A weight file Ollama can pull. Imatrix and vision projectors are not models."""
    name = (path or "").lower()
    if not name.endswith(".gguf"):
        return False
    return "mmproj" not in name and "imatrix" not in name


def moe_from_name(model_id: str) -> bool:
    """Name signals that survive a missing model card. A3B stays MoE even on a distill."""
    text = model_id or ""
    if _MOE_NAME.search(text):
        return True
    if "distill" in text.lower():
        return False
    return _DEEPSEEK_MOE.search(text) is not None


def moe_from_card(info: dict[str, Any]) -> bool:
    gguf = info.get("gguf") if isinstance(info.get("gguf"), dict) else {}
    architecture = gguf.get("architecture") if isinstance(gguf, dict) else ""
    if isinstance(architecture, str) and "moe" in architecture.lower():
        return True
    tags = info.get("tags") if isinstance(info.get("tags"), list) else []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        low = tag.lower()
        if low in {"moe", "mixtral"} or low.endswith("_moe") or "_moe" in low:
            return True
    return False


def is_moe(model_id: str, info: dict[str, Any] | None = None) -> bool:
    if moe_from_name(model_id):
        return True
    if isinstance(info, dict):
        return moe_from_card(info)
    return False


def flags_from_card(info: dict[str, Any], model_id: str = "") -> tuple[bool, bool, bool, bool]:
    """Tools, thinking, vision, and MoE. Same rules as the detail pane."""
    gguf = info.get("gguf") if isinstance(info.get("gguf"), dict) else {}
    template = gguf.get("chat_template") if isinstance(gguf, dict) else ""
    tags = info.get("tags") if isinstance(info.get("tags"), list) else []
    tools, thinking = template_flags(
        template if isinstance(template, str) else "",
        [str(item) for item in tags],
    )
    pipeline = info.get("pipeline_tag")
    vision = pipeline == "image-text-to-text"
    return tools, thinking, vision, is_moe(model_id, info)


def slim_row(row: dict[str, Any]) -> dict[str, Any]:
    """What a search keeps of a Hub row: the sort and filter fields and the flags, not the template."""
    model_id = row.get("modelId") or row.get("id")
    slim = {key: row[key] for key in _ROW_KEEP if key in row}
    slim["flags"] = flags_from_card(row, model_id if isinstance(model_id, str) else "")
    return slim


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


def hub_cooldown() -> int:
    """Seconds before the Hub takes calls again after a 429; 0 when it does."""
    return max(0, math.ceil(_COOLDOWN["until"] - time.monotonic()))


def _rate_limit_wait(headers: Any) -> float:
    """Retry-After, else the reset of the "ratelimit" header (``"api";r=0;t=120``), else a minute."""
    wait = retry_after_seconds(headers)
    if wait is None:
        found = _RATELIMIT_RESET.search(str(headers.get("ratelimit") or ""))
        wait = float(found.group(1)) if found else 60.0
    return min(max(wait, 1.0), _COOLDOWN_MAX)


def hub_error(exc: RuntimeApiError) -> tuple[str, int | None]:
    """The message key for the hub pane, and the seconds to wait when the Hub is rate limiting."""
    key = _HUB_ERRORS.get(exc.error_key, exc.error_key)
    wait = math.ceil(exc.retry_after) if key == "models.hub.rateLimited" and exc.retry_after else None
    return key, wait


def _hub_get(url: str, *, timeout: float) -> Any:
    """One GET to the Hub. During a 429 cooldown nothing is sent."""
    wait = hub_cooldown()
    if wait:
        raise RuntimeApiError("runtime.rateLimited", status=429, retry_after=wait)
    try:
        with client(timeout_sec=timeout) as http:
            response = http.get(url)
    except Exception as exc:
        if is_transport_error(exc):
            raise_transport(exc)
        raise RuntimeApiError("models.hub.failed") from exc
    if response.status_code == 429:
        _COOLDOWN["until"] = max(_COOLDOWN["until"], time.monotonic() + _rate_limit_wait(response.headers))
        raise RuntimeApiError("runtime.rateLimited", status=429, retry_after=hub_cooldown())
    raise_for_status(response)
    return response


def _get_json(url: str) -> Any:
    return response_json(_hub_get(url, timeout=20.0))


def _remember(url: str, value: tuple[list[dict[str, Any]], str | None]) -> None:
    now = time.monotonic()
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            for key in [key for key, (at, _) in _CACHE.items() if now - at >= _CACHE_SEC]:
                del _CACHE[key]
            while len(_CACHE) >= _CACHE_MAX:
                del _CACHE[next(iter(_CACHE))]
        _CACHE[url] = (now, value)


def _search_one(
    pipeline: str,
    *,
    search: str,
    size: str | None,
    sort: str,
    limit: int,
    cursor: str | None,
    deadline: float | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """One page of one task, slimmed. A slow moment gets one more try; a rate limit does not."""
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
    params.extend(("expand[]", field) for field in _EXPAND)
    url = f"{HUB}/api/models?{urlencode(params)}"
    cached = _CACHE.get(url)
    if cached and time.monotonic() - cached[0] < _CACHE_SEC:
        return cached[1]
    response = None
    for attempt in range(2):
        left = _HUB_TIMEOUT if deadline is None else min(_HUB_TIMEOUT, deadline - time.monotonic())
        if left < 1.0:
            raise RuntimeApiError("runtime.timeout")
        try:
            response = _hub_get(url, timeout=left)
            break
        except RuntimeApiError as exc:
            if attempt == 0 and exc.error_key in {"runtime.timeout", "runtime.unreachable", "runtime.upstream"}:
                continue
            raise
    if response is None:
        raise RuntimeApiError("models.hub.failed")
    payload = response_json(response)
    rows = [slim_row(row) for row in (payload if isinstance(payload, list) else []) if isinstance(row, dict)]
    found = (rows, cursor_from_link(response.headers.get("link")))
    _remember(url, found)
    return found


_CAPABILITIES = ("tools", "thinking", "vision")
_SCAN_PAGES = 8  # Hub pages read per request beyond the first page of every task
_VISION_PIPE = "image-text-to-text"
_SCAN_PREFIX = "m1."
_MAX_TAKEN = 1000


def parse_capabilities(raw: str) -> tuple[str, ...]:
    found: list[str] = []
    for part in (raw or "").split(","):
        key = part.strip().lower()
        if key in _CAPABILITIES and key not in found:
            found.append(key)
    return tuple(found)


def capability_filter(must_raw: str, never_raw: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Capabilities a model must have, and those it must not have. "Must not" wins a clash."""
    never = parse_capabilities(never_raw)
    must = tuple(key for key in parse_capabilities(must_raw) if key not in never)
    return must, never


def narrow_pipelines(
    pipes: tuple[str, ...], must: tuple[str, ...], never: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Vision is the image-text-to-text task: filter it by task instead of model by model."""
    if "vision" in never:
        pipes = tuple(pipe for pipe in pipes if pipe != _VISION_PIPE)
    elif "vision" in must:
        pipes = tuple(pipe for pipe in pipes if pipe == _VISION_PIPE)
    return pipes, tuple(key for key in must if key != "vision"), tuple(key for key in never if key != "vision")


def _matches(item: HubHit, must: tuple[str, ...], never: tuple[str, ...] = (), moe: bool = False) -> bool:
    if moe and not item.moe:
        return False
    return all(getattr(item, key) for key in must) and not any(getattr(item, key) for key in never)


def _row_hit(row: dict[str, Any]) -> HubHit | None:
    model_id = row.get("modelId") or row.get("id")
    if not isinstance(model_id, str):
        return None
    downloads = row.get("downloads")
    likes = row.get("likes")
    tag = row.get("pipeline_tag")
    flags = row.get("flags")
    if not (isinstance(flags, tuple) and len(flags) == 4):
        flags = (False, False, False, moe_from_name(model_id))
    tools, thinking, vision, moe = flags
    return HubHit(
        id=model_id,
        pipeline=tag if isinstance(tag, str) else None,
        downloads=int(downloads) if isinstance(downloads, int) else 0,
        likes=int(likes) if isinstance(likes, int) else 0,
        url=f"{HUB}/{model_id}",
        tools=bool(tools),
        thinking=bool(thinking),
        vision=bool(vision),
        moe=bool(moe),
    )


def pack_scan(states: list[dict[str, Any]]) -> str | None:
    """Where each task's reading stands: its Hub page cursor and the rows taken from that page."""
    if all(state["done"] for state in states):
        return None
    rows = [[state["hf"], state["n"], 1 if state["done"] else 0] for state in states]
    raw = base64.urlsafe_b64encode(json.dumps(rows, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{_SCAN_PREFIX}{raw}"


def unpack_scan(token: str | None, count: int) -> list[dict[str, Any]] | None:
    if not token or not token.startswith(_SCAN_PREFIX):
        return None
    body = token[len(_SCAN_PREFIX) :]
    try:
        loaded = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, list) or len(loaded) != count:
        return None
    states: list[dict[str, Any]] = []
    for item in loaded:
        if not isinstance(item, list) or len(item) != 3:
            return None
        hf, taken, done = item
        if hf is not None and (not isinstance(hf, str) or len(hf) > 4000):
            return None
        if not isinstance(taken, int) or isinstance(taken, bool) or not 0 <= taken <= _MAX_TAKEN:
            return None
        states.append({"hf": hf, "n": taken, "done": done == 1})
    return states


_STALLED = object()


def _search_merged(
    *,
    pipes: tuple[str, ...],
    needle: str,
    size_query: str | None,
    sort_key: str,
    page: int,
    cursor: str | None,
    must: tuple[str, ...],
    never: tuple[str, ...],
    moe: bool,
) -> HubSearchResponse:
    """Read every task's Hub results in the Hub's order and merge them by the sort value.

    Each task keeps its own Hub cursor and how many rows of that page are taken, so the
    next request picks up exactly there. With a capability or MoE filter, pages are read
    until the page is full, the page budget is spent or the time is up. A task whose first
    page fails is left out of this page and tried again on the next one; a later failure
    ends the page there.
    """
    states = unpack_scan(cursor, len(pipes)) or [{"hf": None, "n": 0, "done": False} for _ in pipes]
    deadline = time.monotonic() + _SEARCH_SECONDS
    pages: dict[int, tuple[list[tuple[HubHit | None, float | str]], str | None]] = {}
    failed: dict[int, RuntimeApiError] = {}
    budget = _SCAN_PAGES

    def load(index: int) -> bool:
        try:
            rows, nxt = _search_one(
                pipes[index],
                search=needle,
                size=size_query,
                sort=sort_key,
                limit=page,
                cursor=states[index]["hf"],
                deadline=deadline,
            )
        except RuntimeApiError as exc:
            failed[index] = exc  # not done: the next page starts this task from the same place
            return False
        pages[index] = (
            [(_row_hit(row) if keep_hub_row(row, pipes) else None, sort_value(row, sort_key)) for row in rows],
            nxt,
        )
        return True

    def head(index: int) -> Any:
        nonlocal budget
        state = states[index]
        while not state["done"] and index not in failed:
            if index not in pages:
                if budget <= 0 or time.monotonic() >= deadline:
                    return _STALLED
                budget -= 1
                if not load(index):
                    return _STALLED
            entries, nxt = pages[index]
            if state["n"] < len(entries):
                return entries[state["n"]]
            del pages[index]
            if not nxt:
                states[index] = {"hf": None, "n": 0, "done": True}
                return None
            state["hf"], state["n"] = nxt, 0
        return None

    first = [index for index, state in enumerate(states) if not state["done"]]
    if first:
        with ThreadPoolExecutor(max_workers=len(first)) as pool:
            list(pool.map(load, first))
    collected: list[HubHit] = []
    seen: set[str] = set()
    while len(collected) < page:
        best: tuple[int, tuple[HubHit | None, float | str]] | None = None
        stalled = False
        for index in range(len(pipes)):
            entry = head(index)
            if entry is _STALLED:
                stalled = True
                break
            if entry is not None and (best is None or entry[1] > best[1][1]):
                best = (index, entry)
        if stalled or best is None:
            break
        index, (hit, _) = best
        states[index]["n"] += 1
        if hit is None or hit.id in seen or not _matches(hit, must, never, moe):
            continue
        seen.add(hit.id)
        collected.append(hit)
    if not collected and failed:
        key, wait = hub_error(next(iter(failed.values())))
        return HubSearchResponse(items=[], page_size=page, message_key=key, retry_after=wait)
    token = pack_scan(states)
    return HubSearchResponse(items=collected, page_size=page, has_next=token is not None, next_cursor=token)


def search_hub(
    *,
    search: str,
    pipeline: str,
    size: str,
    sort: str,
    limit: int = _DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
    capabilities: str = "",
    without: str = "",
) -> HubSearchResponse:
    """GGUF models of the chosen tasks, merged by the sort value (the Hub sorts descending only)."""
    tasks, moe = type_selection(pipeline)
    must, never = capability_filter(capabilities, without)
    pipes, must, never = narrow_pipelines(pipeline_tags(tasks or "all"), must, never)
    page = page_limit(limit)
    if not pipes:
        return HubSearchResponse(items=[], page_size=page)
    return _search_merged(
        pipes=pipes,
        needle=search.strip()[:80],
        size_query=parameter_query(size),
        sort_key=hf_sort_key(sort),
        page=page,
        cursor=cursor,
        must=must,
        never=never,
        moe=moe,
    )


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
        key, wait = hub_error(exc)
        return HubFilesResponse(id=repo, url=url, installable=False, message_key=key, retry_after=wait)
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
        parameters=parameter_label(info),
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
        moe=is_moe(repo, info),
        installable=installable,
        reason=reason,
        quants=quants,
    )
