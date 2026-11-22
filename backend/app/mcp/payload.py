"""Shape MCP arguments and results for models."""

from __future__ import annotations

import copy
import json
from typing import Any

TOOL_RESULT_CHARS = 4000
# Below this budget a structured cut makes no sense; the plain cut stays.
_STRUCTURED_MIN = 200
# A string that is shortened keeps at least this much.
_KEEP_MIN = 120
# Longest "[... N characters omitted ...]" marker with its two line breaks.
_MARK_ROOM = 40
_SEARCH_ITEM_KEYS = (
    "full_name",
    "name",
    "description",
    "html_url",
    "private",
    "language",
    "stargazers_count",
)


def coerce_tool_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, float) and value.is_integer():
            out[key] = int(value)
        elif isinstance(value, dict):
            out[key] = coerce_tool_arguments(value)
        elif isinstance(value, list):
            out[key] = [
                coerce_tool_arguments(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            out[key] = value
    return out


def compact_tool_result(value: object) -> object:
    """Keep GitHub-style search payloads to name/url rows."""
    if not isinstance(value, dict):
        return value
    items = value.get("items")
    if not isinstance(items, list) or "total_count" not in value:
        return value
    compact_items: list[dict[str, Any]] = []
    for raw in items[:15]:
        if not isinstance(raw, dict):
            continue
        row = {key: raw[key] for key in _SEARCH_ITEM_KEYS if key in raw}
        if row:
            compact_items.append(row)
    return {
        "total_count": value.get("total_count"),
        "incomplete_results": value.get("incomplete_results"),
        "items": compact_items,
    }


def clip_middle(text: str, limit: int) -> str:
    """Keep head and tail of a long text. The marker says how much is missing.

    The result is never longer than ``limit`` (for limits above the marker size).
    """
    if len(text) <= limit:
        return text
    room = max(0, limit - _MARK_ROOM)
    head = int(room * 0.7)
    tail = room - head
    omitted = len(text) - head - tail
    ending = text[len(text) - tail :] if tail else ""
    return f"{text[:head]}\n[... {omitted} characters omitted ...]\n{ending}"


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _longest_string(value: object, path: tuple = ()) -> tuple[tuple | None, int]:
    best_path: tuple | None = None
    best_len = 0
    if isinstance(value, str):
        return path, len(value)
    if isinstance(value, dict):
        for key, nested in value.items():
            found, size = _longest_string(nested, (*path, key))
            if found is not None and size > best_len:
                best_path, best_len = found, size
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found, size = _longest_string(nested, (*path, index))
            if found is not None and size > best_len:
                best_path, best_len = found, size
    return best_path, best_len


def _get(value: Any, path: tuple) -> Any:
    for key in path:
        value = value[key]
    return value


def _set(value: Any, path: tuple, new: object) -> None:
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = new


def _fit_json(value: object, limit: int) -> str:
    """Shorten the longest strings until the JSON fits. The result stays valid JSON."""
    work = copy.deepcopy(value)
    # Room for the "truncated" flag added below.
    target = limit - 24
    cut = False
    for _ in range(24):
        text = _dump(work)
        if len(text) <= target:
            break
        path, size = _longest_string(work)
        if not path or size <= _KEEP_MIN:
            break
        over = len(text) - target
        keep = max(_KEEP_MIN, size - over)
        if keep >= size:
            # Escaping made the JSON longer than the raw string; cut harder.
            keep = max(_KEEP_MIN, size // 2)
        _set(work, path, clip_middle(_get(work, path), keep))
        cut = True
    text = _dump(work)
    if len(text) <= target:
        if cut and isinstance(work, dict):
            work["truncated"] = True
            text = _dump(work)
        return text
    # Many small values: no single string to shorten. Wrap a preview instead.
    preview = text[: max(0, limit - 120)]
    for _ in range(12):
        wrapped = _dump({"truncated": True, "totalChars": len(text), "preview": preview})
        if len(wrapped) <= limit:
            return wrapped
        preview = preview[: int(len(preview) * 0.8)]
    return _dump({"truncated": True, "totalChars": len(text)})


def format_tool_result(value: object, *, limit: int = TOOL_RESULT_CHARS) -> str:
    """Serialize one tool result for the model, within ``limit`` characters.

    A result that is too long is shortened inside its strings (head and tail
    stay) and flagged with ``truncated``. It is not cut in the middle of the
    JSON: fields after a long string (``bytes``, ``stderr``, ``timedOut``) must
    survive, and the model must be able to tell that something is missing.
    """
    compact = compact_tool_result(value)
    if isinstance(compact, str):
        if len(compact) <= limit:
            return compact
        if limit < _STRUCTURED_MIN:
            return compact[:limit] + "\n… truncated"
        return clip_middle(compact, limit)
    text = _dump(compact)
    if len(text) <= limit:
        return text
    if limit < _STRUCTURED_MIN:
        return text[:limit] + "\n… truncated"
    return _fit_json(compact, limit)
