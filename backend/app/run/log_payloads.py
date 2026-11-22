"""Small, readable payloads for run log lines (B2, B3, B5, B6).

The log keeps what a person needs to follow a run: the task, the result, what a
tool did. Long texts (file contents, model answers) are clipped here; the model
itself always gets the full text.
"""

from __future__ import annotations

from app.run.limits import LOG_ARG_MAX

# Keys of a tool result that are short facts worth keeping as they are.
_FACT_KEYS = (
    "path",
    "from",
    "bytes",
    "size",
    "startLine",
    "endLine",
    "nextOffset",
    "replacements",
    "deleted",
    "existed",
    "dryRun",
    "truncated",
    "exitCode",
    "timedOut",
    # Terminal: a server or watch command that was stopped after its start window.
    "running",
    "stoppedAfterSec",
    "status",
    "statusCode",
    "pattern",
    "type",
)
# Keys holding lists: only their length is kept.
_LIST_KEYS = ("entries", "matches", "files", "children", "results", "items")
_LINE_MAX = 200


def clip(text: str, limit: int) -> str:
    """``text`` up to ``limit`` characters, with a marker how much was cut."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… [+{len(text) - limit}]"


def clip_strings(value: object, limit: int = LOG_ARG_MAX) -> object:
    """Every string inside ``value`` clipped to ``limit`` (file contents in tool arguments)."""
    if isinstance(value, str):
        return clip(value, limit)
    if isinstance(value, dict):
        return {str(key): clip_strings(item, limit) for key, item in value.items()}
    if isinstance(value, list):
        return [clip_strings(item, limit) for item in value]
    return value


def one_line(text: str, limit: int = _LINE_MAX) -> str:
    return clip(" ".join((text or "").split()), limit)


def _first_line(text: object) -> str:
    if not isinstance(text, str):
        return ""
    for line in text.splitlines():
        if line.strip():
            return one_line(line)
    return ""


def _last_line(text: object) -> str:
    if not isinstance(text, str):
        return ""
    for line in reversed(text.splitlines()):
        if line.strip():
            return one_line(line)
    return ""


def _line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def tool_result_summary(tool_result: object) -> dict | None:
    """Facts of a tool result: path, sizes, counts, exit code, first error line.

    ``tool_result`` is the dict a first-party tool returns (``{ok, result, errorKey}``),
    or what an MCP server answered.
    """
    inner = tool_result
    if isinstance(tool_result, dict) and "ok" in tool_result and "result" in tool_result:
        inner = tool_result.get("result")
    if isinstance(inner, str):
        return {"chars": len(inner)} if inner else None
    if isinstance(inner, list):
        return {"items": len(inner)}
    if not isinstance(inner, dict):
        return None
    out: dict = {}
    for key in _FACT_KEYS:
        value = inner.get(key)
        if isinstance(value, (str, int, float, bool)) and value != "":
            out[key] = clip(value, _LINE_MAX) if isinstance(value, str) else value
    for key in _LIST_KEYS:
        value = inner.get(key)
        if isinstance(value, list):
            out[key] = len(value)
    content = inner.get("content")
    if isinstance(content, str):
        out["lines"] = _line_count(content)
    if "exitCode" in inner:
        # Terminal: the line that tells what went wrong, or the last line of the output.
        code = inner.get("exitCode")
        if code not in (0, None) or inner.get("timedOut"):
            line = _first_line(inner.get("stderr")) or _last_line(inner.get("stdout"))
        else:
            line = _last_line(inner.get("stdout")) or _last_line(inner.get("stderr"))
        if line:
            out["output"] = line
    return out or None
