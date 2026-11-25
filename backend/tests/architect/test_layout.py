"""Where the architect puts nodes: close together, helpers next to what they serve, no overlaps."""

from __future__ import annotations

from app.architect.layout import COLUMN_GAP, arrange, layout, node_sizes


def _node(node_id: str, kind: str, name: str | None = None) -> dict:
    return {"id": node_id, "type": kind, "data": {"displayName": name} if name else {}}


def _edge(source: str, target: str, source_handle: str = "message", target_handle: str = "message") -> dict:
    return {"id": f"{source}-{target}", "source": source, "target": target, "sourceHandle": source_handle, "targetHandle": target_handle}


def _team() -> tuple[list[dict], list[dict]]:
    """The coder team from the user's example: a chief, three agents, shared tool and models."""
    nodes = [
        _node("chat", "chat_input", "chat_input"),
        _node("chef", "orchestrator", "Chef Coder"),
        _node("junior", "agent", "Junior"),
        _node("senior", "agent", "Senior"),
        _node("architekt", "agent", "Architekt"),
        _node("big", "llm", "Qwen 36B"),
        _node("small", "llm", "Qwen 4B"),
        _node("llm", "llm", "llm"),
        _node("tool", "tool", "tool"),
        _node("end", "end", "end"),
    ]
    edges = [_edge("chat", "chef"), _edge("chef", "end")]
    for agent in ("junior", "senior", "architekt"):
        edges.append(_edge("chef", agent, f"channel:{agent}", "channel"))
        edges.append(_edge("tool", agent, "tool", "tool"))
    edges += [
        _edge("big", "chef", "llm", "llm"),
        _edge("tool", "chef", "tool", "tool"),
        _edge("small", "junior", "llm", "llm"),
        _edge("llm", "senior", "llm", "llm"),
        _edge("llm", "architekt", "llm", "llm"),
    ]
    return nodes, edges


def _rects(nodes: list[dict], edges: list[dict], positions: dict) -> dict[str, tuple[float, float, float, float]]:
    sizes = node_sizes(nodes, edges)
    return {
        node_id: (pos["x"], pos["y"], pos["x"] + sizes[node_id][0], pos["y"] + sizes[node_id][1])
        for node_id, pos in positions.items()
    }


def _assert_apart(rects: dict[str, tuple[float, float, float, float]], gap: float = 24) -> None:
    ids = list(rects)
    for index, a in enumerate(ids):
        for b in ids[index + 1 :]:
            ax0, ay0, ax1, ay1 = rects[a]
            bx0, by0, bx1, by1 = rects[b]
            apart = ax1 + gap <= bx0 or bx1 + gap <= ax0 or ay1 + gap <= by0 or by1 + gap <= ay0
            assert apart, (a, rects[a], b, rects[b])


def test_a_team_stays_together_with_helpers_beside_their_users() -> None:
    nodes, edges = _team()
    positions = arrange(nodes, edges)
    rects = _rects(nodes, edges, positions)
    _assert_apart(rects)
    x = {node_id: pos["x"] for node_id, pos in positions.items()}
    # The flow reads left to right; the end sits with the agents behind the chief.
    assert x["chat"] < x["chef"] < x["junior"] == x["senior"] == x["architekt"] == x["end"]
    # Each helper sits in the column just left of its leftmost user, not below the network.
    for helper, user in (("big", "chef"), ("tool", "chef"), ("small", "junior"), ("llm", "senior")):
        gap = rects[user][0] - rects[helper][2]
        assert 0 < gap <= COLUMN_GAP + 1, (helper, gap)
        helper_mid = (rects[helper][1] + rects[helper][3]) / 2
        assert rects[user][1] - 200 <= helper_mid <= rects[user][3] + 200, (helper, helper_mid, rects[user])
    # Compact: wider than tall, like the example, and nothing stacked far below the flow.
    width = max(r[2] for r in rects.values()) - min(r[0] for r in rects.values())
    height = max(r[3] for r in rects.values()) - min(r[1] for r in rects.values())
    flow_bottom = max(rects[node_id][3] for node_id in ("chef", "junior", "senior", "architekt", "end"))
    assert height < width
    assert max(r[3] for r in rects.values()) <= flow_bottom + 120


def test_an_agents_model_tool_and_knowledge_stack_beside_it() -> None:
    nodes = [
        _node("chat", "chat_input"),
        _node("writer", "agent", "Geschichtenschreiber"),
        _node("model", "llm", "claude-fable-5-2"),
        _node("files", "tool", "Dateizugriff"),
        _node("docs", "knowledge", "Vorbilder"),
        _node("end", "end"),
    ]
    edges = [
        _edge("chat", "writer"),
        _edge("writer", "end"),
        _edge("model", "writer", "llm", "llm"),
        _edge("files", "writer", "tool", "tool"),
        _edge("docs", "writer", "knowledge", "knowledge"),
    ]
    positions = arrange(nodes, edges)
    rects = _rects(nodes, edges, positions)
    _assert_apart(rects)
    for helper in ("model", "files", "docs"):
        assert rects[helper][2] < rects["writer"][0]
    # In port order from top to bottom: model, tool, knowledge.
    assert positions["model"]["y"] < positions["files"]["y"] < positions["docs"]["y"]
    assert positions["chat"]["x"] < positions["writer"]["x"] < positions["end"]["x"]


def test_new_nodes_follow_their_kept_neighbour() -> None:
    nodes, edges = _team()
    keep = {node["id"]: {"x": 2000 + index * 10, "y": 3000} for index, node in enumerate(nodes) if node["id"] != "small"}
    # Spread the kept nodes like a real layout so they do not overlap each other.
    fresh = arrange(nodes, edges)
    keep = {node_id: {"x": fresh[node_id]["x"] + 1000, "y": fresh[node_id]["y"] + 500} for node_id in keep}
    layout(nodes, edges, keep)
    placed = {node["id"]: node["position"] for node in nodes}
    for node_id, position in keep.items():
        assert placed[node_id] == position
    # The new model lands next to the agent it serves, in the kept network's frame.
    assert abs(placed["small"]["x"] - (fresh["small"]["x"] + 1000)) <= 16
    _assert_apart(_rects(nodes, edges, placed), gap=1)
