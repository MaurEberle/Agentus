from __future__ import annotations

from typing import Any

from app.mcp.models import McpToolInfo


class FakeSession:
    def __init__(
        self,
        *,
        tools: list[McpToolInfo] | None = None,
        result: Any = "ok",
        is_error: bool = False,
    ) -> None:
        self.tools = tools or [
            McpToolInfo(name="search", description="s", input_schema={"type": "object"})
        ]
        self.result = result
        self.is_error = is_error
        self.closed = False
        self.calls: list[tuple[str, dict]] = []

    def list_tools(self) -> list[McpToolInfo]:
        return self.tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return {"isError": self.is_error, "result": self.result}

    def close(self) -> None:
        self.closed = True
