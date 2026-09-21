"""Per-agent channel between an orchestrator and an agent.

The orchestrator message port stays the end of the run. Each agent gets
`channel:<agentId>`. A stored message edge from orchestrator to agent is
rewritten so older graphs keep running.
"""

from __future__ import annotations

from app.run.graph_models import AgentNetworkDocument, GraphEdge


def channel_handle(agent_id: str) -> str:
    return f"channel:{agent_id}"


def agent_id_from_channel(handle: str) -> str | None:
    prefix = "channel:"
    if not handle.startswith(prefix):
        return None
    agent_id = handle[len(prefix) :]
    return agent_id or None


def normalize_channel_edges(doc: AgentNetworkDocument) -> AgentNetworkDocument:
    by_id = {node.id: node for node in doc.nodes}
    changed = False
    edges: list[GraphEdge] = []
    for edge in doc.edges:
        src = by_id.get(edge.source)
        dst = by_id.get(edge.target)
        if (
            src is not None
            and dst is not None
            and src.type == "orchestrator"
            and dst.type == "agent"
            and edge.source_handle == "message"
            and edge.target_handle == "message"
        ):
            changed = True
            edges.append(
                edge.model_copy(
                    update={
                        "source_handle": channel_handle(dst.id),
                        "target_handle": "channel",
                    }
                )
            )
        else:
            edges.append(edge)
    if not changed:
        return doc
    return doc.model_copy(update={"edges": edges})
