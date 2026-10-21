from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.tools.datetime_tool import DATE_ACTION_ORDER
from app.tools.file_access_tool import FILE_ACTION_ORDER
from app.tools.kinds import FIRST_PARTY_KINDS, FirstPartyKind
from app.tools.models import CatalogGroup, CatalogTool

HTTP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["url"],
    "properties": {
        "url": {"type": "string", "description": "http or https URL"},
        "method": {
            "type": "string",
            "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
        },
        "headers": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        "query": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        "body": {
            "type": "string",
            "description": "Request body for POST/PUT/PATCH",
        },
    },
}

WEB_SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["query"],
    "properties": {
        "query": {"type": "string", "minLength": 1, "maxLength": 500},
    },
}

DATETIME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {
            "type": "string",
            "enum": list(DATE_ACTION_ORDER),
            "description": "now, add, diff, parts, or convert. Default now.",
        },
        "timezone": {"type": "string", "description": "IANA timezone, default UTC"},
        "at": {
            "type": "string",
            "description": "ISO-8601 instant for add, parts, and convert. Naive values use timezone. Default is now.",
        },
        "toTimezone": {"type": "string", "description": "convert: target IANA timezone"},
        "start": {"type": "string", "description": "diff: start ISO-8601"},
        "end": {"type": "string", "description": "diff: end ISO-8601"},
        "days": {"type": "integer", "description": "add: whole days, negative subtracts"},
        "hours": {"type": "integer", "description": "add: hours, negative subtracts"},
        "minutes": {"type": "integer", "description": "add: minutes, negative subtracts"},
    },
}

CALCULATOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["expression"],
    "properties": {
        "expression": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "description": (
                "Arithmetic expression. Operators + - * / // % ** and parentheses. "
                "Functions sqrt, cbrt, abs, round, floor, ceil, min, max, log, ln, log10, exp, sin, cos, tan, factorial. "
                "Names pi and e."
            ),
        },
    },
}

FILE_ACCESS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "path"],
    "properties": {
        "action": {
            "type": "string",
            "enum": list(FILE_ACTION_ORDER),
            "description": "Filesystem operation under the configured root",
        },
        "path": {
            "type": "string",
            "description": "Path relative to the tool root, or '.' for the root itself",
        },
        "content": {
            "type": "string",
            "description": "File contents for write (utf-8 text or base64)",
        },
        "encoding": {
            "type": "string",
            "enum": ["utf-8", "base64"],
            "description": "utf-8 (default) or base64 for binary",
        },
        "recursive": {
            "type": "boolean",
            "description": "Create missing parent directories for mkdir",
        },
        "head": {"type": "integer", "description": "read: return only the first N lines"},
        "tail": {"type": "integer", "description": "read: return only the last N lines"},
        "paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "read_many: file paths under the root",
        },
        "destination": {
            "type": "string",
            "description": "move: destination path under the root",
        },
        "pattern": {
            "type": "string",
            "description": "search: glob matched against the relative path and the file name",
        },
        "oldText": {"type": "string", "description": "edit: text to replace, must occur once"},
        "newText": {"type": "string", "description": "edit: replacement text"},
        "edits": {
            "type": "array",
            "description": "edit: several oldText/newText pairs, applied in order",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["oldText", "newText"],
                "properties": {
                    "oldText": {"type": "string"},
                    "newText": {"type": "string"},
                },
            },
        },
        "dryRun": {"type": "boolean", "description": "edit: report the change without writing"},
    },
}

_MODEL_DESCRIPTIONS: dict[FirstPartyKind, str] = {
    "http": "Fetch an http or https URL and return status, headers, and body.",
    "web_search": "Search the web and return titles, URLs, and snippets. The provider is chosen in the tool settings.",
    "datetime": (
        "Work with instants. action now returns the current time. "
        "add shifts at (or now) by days, hours, and minutes; negative values subtract. "
        "diff returns seconds, hours, and days between start and end. "
        "parts splits an instant into year, month, day, hour, minute, second, weekday, and weekdayIndex (Monday is 1). "
        "convert shows the same instant in toTimezone. "
        "timezone is an IANA name, default UTC. at, start, and end are ISO-8601; naive values use timezone."
    ),
    "calculator": (
        "Evaluate an arithmetic expression. Operators: + - * / // % ** and parentheses. "
        "The ** exponent must be at most 20. Names: pi, e. "
        "Functions: sqrt, cbrt, abs, round, floor, ceil, min, max, log, ln, log10, exp, sin, cos, tan, factorial. "
        "log(x) and ln(x) are natural; log(x, base) takes a base. "
        "sin, cos, tan use radians. factorial takes an integer from 0 to 20."
    ),
    "file_access": "Read and write files under the configured root. Actions: list, stat, read (optional head or tail), read_many, write (creates missing parent folders), mkdir, delete, edit (oldText/newText or edits), move (destination), search (pattern), tree.",
}

_mcp_provider: Callable[[], list[CatalogGroup]] | None = None


def set_mcp_catalog_provider(
    provider: Callable[[], list[CatalogGroup]] | None,
) -> None:
    global _mcp_provider
    _mcp_provider = provider


def reset_mcp_catalog_provider() -> None:
    set_mcp_catalog_provider(None)


def list_first_party_tools() -> list[CatalogTool]:
    return [
        CatalogTool(
            name="http",
            kind="http",
            description=_MODEL_DESCRIPTIONS["http"],
            json_schema=HTTP_SCHEMA,
            credential_kind=None,
            title_key="tools.kind.http",
            description_key="tools.kind.http.desc",
        ),
        CatalogTool(
            name="web_search",
            kind="web_search",
            description=_MODEL_DESCRIPTIONS["web_search"],
            json_schema=WEB_SEARCH_SCHEMA,
            credential_kind=None,
            title_key="tools.kind.webSearch",
            description_key="tools.kind.webSearch.desc",
        ),
        CatalogTool(
            name="datetime",
            kind="datetime",
            description=_MODEL_DESCRIPTIONS["datetime"],
            json_schema=DATETIME_SCHEMA,
            credential_kind=None,
            title_key="tools.kind.datetime",
            description_key="tools.kind.datetime.desc",
        ),
        CatalogTool(
            name="calculator",
            kind="calculator",
            description=_MODEL_DESCRIPTIONS["calculator"],
            json_schema=CALCULATOR_SCHEMA,
            credential_kind=None,
            title_key="tools.kind.calculator",
            description_key="tools.kind.calculator.desc",
        ),
        CatalogTool(
            name="file_access",
            kind="file_access",
            description=_MODEL_DESCRIPTIONS["file_access"],
            json_schema=FILE_ACCESS_SCHEMA,
            credential_kind=None,
            title_key="tools.kind.fileAccess",
            description_key="tools.kind.fileAccess.desc",
        ),
    ]


def list_catalog_groups() -> list[CatalogGroup]:
    groups = [
        CatalogGroup(
            id="firstParty",
            title_key="tools.group.firstParty",
            tools=list_first_party_tools(),
        )
    ]
    if _mcp_provider is not None:
        groups.extend(_mcp_provider())
    return groups


def _file_access_parameters(actions: list[str] | None) -> tuple[dict[str, Any], str]:
    schema = dict(FILE_ACCESS_SCHEMA)
    properties = dict(schema.get("properties") or {})
    action = dict(properties.get("action") or {})
    chosen = list(FILE_ACTION_ORDER) if actions is None else [name for name in FILE_ACTION_ORDER if name in actions]
    action["enum"] = chosen
    properties["action"] = action
    schema["properties"] = properties
    description = _MODEL_DESCRIPTIONS["file_access"]
    if actions is not None:
        description = "File actions under the configured root: " + ", ".join(chosen) + "."
    return schema, description


def openai_tools_for_kinds(
    kinds: list[str], *, file_actions: list[str] | None = None
) -> list[dict[str, Any]]:
    by_name = {tool.name: tool for tool in list_first_party_tools()}
    out: list[dict[str, Any]] = []
    for kind in kinds:
        tool = by_name.get(kind)
        if tool is None or tool.json_schema is None:
            continue
        parameters = tool.json_schema
        description = tool.description or _MODEL_DESCRIPTIONS[tool.name]  # type: ignore[index]
        if kind == "file_access":
            if file_actions is not None and not file_actions:
                continue
            parameters, description = _file_access_parameters(file_actions)
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": description,
                    "parameters": parameters,
                },
            }
        )
    return out


def first_party_kind(kind: str) -> FirstPartyKind | None:
    if kind in FIRST_PARTY_KINDS:
        return kind  # type: ignore[return-value]
    return None
