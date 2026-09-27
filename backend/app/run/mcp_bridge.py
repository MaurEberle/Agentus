from __future__ import annotations

from typing import Any, Protocol

from app.mcp.names import openai_tools_for_server, parse_openai_tool_name
from app.mcp.models import McpToolInfo


class McpSessions(Protocol):
    def open_for(
        self,
        server_ids: list[str],
        credential_overrides: dict[str, str] | None = None,
        root_overrides: dict[str, str] | None = None,
    ) -> None: ...

    def close_all(self) -> None: ...

    def call(self, server_id: str, tool_name: str, arguments: dict) -> dict: ...

    def is_enabled(self, server_id: str) -> bool: ...

    def root_path(self, server_id: str) -> str | None: ...

    def listed_tools(self, server_id: str) -> list[McpToolInfo]: ...


def validation_kwargs() -> dict[str, Any]:
    mcp = get_mcp()
    return {
        "mcp_available": mcp is not None,
        "mcp_enabled": mcp.is_enabled if mcp else None,
        "mcp_root": mcp.root_path if mcp else None,
    }


def get_mcp() -> McpSessions | None:
    try:
        from app.mcp.sessions import SESSIONS

        return SESSIONS
    except ImportError:
        return None


def map_openai_tool_name(name: str) -> tuple[str, str] | None:
    return parse_openai_tool_name(name)


def mcp_openai_tools(server_id: str, tools: list[McpToolInfo]) -> list[dict[str, Any]]:
    return openai_tools_for_server(server_id, tools)
