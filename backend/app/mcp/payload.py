"""Shape MCP arguments and results for models."""

from __future__ import annotations

import json
from typing import Any

TOOL_RESULT_CHARS = 4000
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


def format_tool_result(value: object, *, limit: int = TOOL_RESULT_CHARS) -> str:
    compact = compact_tool_result(value)
    if isinstance(compact, str):
        text = compact
    else:
        text = json.dumps(compact, ensure_ascii=False)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n… truncated"
