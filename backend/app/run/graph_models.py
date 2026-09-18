from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.http.app import ApiModel

NodeType = Literal[
    "chat_input", "llm", "agent", "tool", "knowledge", "router", "end"
]


class GraphNode(ApiModel):
    id: str
    type: str
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(ApiModel):
    id: str
    source: str
    source_handle: str = Field(default="message", alias="sourceHandle")
    target: str
    target_handle: str = Field(default="message", alias="targetHandle")


class AgentNetworkDocument(ApiModel):
    schema_version: int = Field(alias="schemaVersion")
    id: str | None = None
    name: str = ""
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    updated_at: str | None = Field(default=None, alias="updatedAt")
    viewport: dict[str, Any] | None = None
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
