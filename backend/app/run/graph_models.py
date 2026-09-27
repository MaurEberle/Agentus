from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.http.app import ApiModel

NodeType = Literal[
    "chat_input", "orchestrator", "llm", "agent", "tool", "mcp", "knowledge", "router", "end"
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


def is_mcp_node(node: GraphNode) -> bool:
    return node.type == "mcp" or (node.type == "tool" and str(node.data.get("kind") or "") == "mcp")


def normalize_mcp_nodes(doc: AgentNetworkDocument) -> AgentNetworkDocument:
    """Rewrite tool nodes with kind=mcp into type=mcp so older graphs keep running."""
    changed = False
    nodes: list[GraphNode] = []
    for node in doc.nodes:
        if node.type == "tool" and str(node.data.get("kind") or "") == "mcp":
            data = dict(node.data)
            data.pop("kind", None)
            nodes.append(node.model_copy(update={"type": "mcp", "data": data}))
            changed = True
        else:
            nodes.append(node)
    if not changed:
        return doc
    return doc.model_copy(update={"nodes": nodes})
