from __future__ import annotations

from collections.abc import Callable
from typing import Any

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
        "timezone": {"type": "string", "description": "IANA timezone, default UTC"},
    },
}

CALCULATOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["expression"],
    "properties": {
        "expression": {"type": "string", "minLength": 1, "maxLength": 200},
    },
}

_MODEL_DESCRIPTIONS: dict[FirstPartyKind, str] = {
    "http": "Fetch an http or https URL and return status, headers, and body.",
    "web_search": "Search the web via Brave Search and return titles, URLs, and snippets.",
    "datetime": "Return the current time in an IANA timezone (default UTC).",
    "calculator": "Evaluate a basic arithmetic expression and return the number.",
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
            credential_kind="web_search",
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


def openai_tools_for_kinds(kinds: list[str]) -> list[dict[str, Any]]:
    by_name = {tool.name: tool for tool in list_first_party_tools()}
    out: list[dict[str, Any]] = []
    for kind in kinds:
        tool = by_name.get(kind)
        if tool is None or tool.json_schema is None:
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or _MODEL_DESCRIPTIONS[tool.name],  # type: ignore[index]
                    "parameters": tool.json_schema,
                },
            }
        )
    return out


def first_party_kind(kind: str) -> FirstPartyKind | None:
    if kind in FIRST_PARTY_KINDS:
        return kind  # type: ignore[return-value]
    return None
