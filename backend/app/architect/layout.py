"""Where the architect puts the nodes of a draft.

The flow runs in columns from left to right. Every model, tool, MCP server and knowledge folder
sits in the column just left of the node it serves, at the height of the port it feeds, so the
network reads as one close group instead of a long column of helpers below it. Nodes keep a gap
to each other; sizes follow the editor's node rendering (frontend canvas/handles.ts).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FLOW_TYPES = frozenset({"chat_input", "orchestrator", "agent", "router", "end"})
SUPPORT_TYPES = frozenset({"llm", "tool", "mcp", "knowledge"})

GRID = 16
MARGIN = 64
# Room for the edges between two columns.
COLUMN_GAP = 112
# Between two nodes of one column.
NODE_GAP = 40

# The editor's node box (canvas/handles.ts): one handle row per port, at least a header.
_HANDLE_ROW = 32
_CHROME = 16
_HEADER = 52
_MIN_WIDTH = 160
_MAX_WIDTH = 420
# The longest port names the editor shows (German is the widest of the UI languages).
_PORT_LABEL = {
    "message": "Nachricht",
    "llm": "LLM",
    "tool": "Werkzeug",
    "knowledge": "Wissen",
    "channel": "Kanal",
    "handoff": "Übergabe",
    "default": "Standard",
}
_TYPE_LABEL = {
    "chat_input": "Chat",
    "orchestrator": "Orchestrator",
    "agent": "Agent",
    "router": "Router",
    "end": "Ende",
    "llm": "LLM",
    "tool": "Werkzeug",
    "mcp": "MCP",
    "knowledge": "Wissen",
}


@dataclass
class _Box:
    width: float
    height: float
    ins: list[str]


def _snap(value: float) -> int:
    return int(round(value / GRID) * GRID)


def _catalog_ports() -> dict[str, tuple[list[str], list[str]]]:
    from app.common.components import node_types

    out: dict[str, tuple[list[str], list[str]]] = {}
    for spec in node_types():
        ports = [port for port in spec.get("ports") or [] if isinstance(port, dict)]
        out[str(spec["type"])] = (
            [str(port["id"]) for port in ports if port.get("direction") == "in"],
            [str(port["id"]) for port in ports if port.get("direction") == "out"],
        )
    return out


def _name(node: dict[str, Any]) -> str:
    name = str((node.get("data") or {}).get("displayName") or "").strip()
    return name or str(node["type"])


def _boxes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, _Box]:
    """Estimated size and input order of every node, as the editor draws it."""
    catalog = _catalog_ports()
    by_id = {node["id"]: node for node in nodes}
    boxes: dict[str, _Box] = {}
    for node in nodes:
        ins, outs = catalog.get(str(node["type"]), ([], []))
        ins, outs = list(ins), list(outs)
        out_labels = [_PORT_LABEL.get(port, port) for port in outs]
        if node["type"] == "orchestrator":
            # One output per agent channel, the free "Kanal" output, then the message output.
            channels: list[str] = []
            for edge in edges:
                handle = str(edge.get("sourceHandle") or "")
                if edge["source"] == node["id"] and handle.startswith("channel:") and handle not in channels:
                    channels.append(handle)
            out_labels = [_name(by_id.get(handle.split(":", 1)[1], {"type": "agent"})) for handle in channels]
            out_labels += [_PORT_LABEL["channel"], _PORT_LABEL["message"]]
        elif node["type"] == "router":
            branches = [item for item in (node.get("data") or {}).get("branches") or [] if isinstance(item, dict)]
            out_labels = [str(item.get("name") or item.get("id") or "") for item in branches if item.get("id") != "default"]
            out_labels.append(_PORT_LABEL["default"])
        rows = max(len(ins), len(out_labels), 1)
        height = max(_HEADER, _CHROME + rows * _HANDLE_ROW)
        # px-3 on both sides, icon and gap, the wider of name (text-sm) and type (text-xs).
        width = 24 + 16 + 8 + max(len(_name(node)) * 7.6, len(_TYPE_LABEL.get(str(node["type"]), "")) * 6.4)
        # Port names (10px) show when a side has more than one port.
        if len(ins) > 1:
            width += 12 + max(len(_PORT_LABEL.get(port, port)) for port in ins) * 5.8
        if len(out_labels) > 1:
            width += 12 + max(len(label) for label in out_labels) * 5.8
        boxes[node["id"]] = _Box(width=min(_MAX_WIDTH, max(_MIN_WIDTH, width)), height=height, ins=ins)
    return boxes


def node_sizes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    """Estimated width and height of every node in the editor."""
    return {node_id: (box.width, box.height) for node_id, box in _boxes(nodes, edges).items()}


def _port_offset(box: _Box, handle: str | None) -> float:
    """How far below the node's top an input port sits (handleTopPercent in the editor)."""
    count = len(box.ins)
    if count <= 1 or handle not in box.ins:
        return box.height / 2
    return box.height * (box.ins.index(str(handle)) + 1) / (count + 1)


def _depths(flow: list[str], edges: list[dict[str, Any]]) -> dict[str, int]:
    """Longest path from the start. An end follows right after what leads to it; behind an
    orchestrator that is the agents' column, below them, not a column of its own."""
    incoming: dict[str, list[str]] = {node_id: [] for node_id in flow}
    for edge in edges:
        if edge["source"] in incoming and edge["target"] in incoming:
            incoming[edge["target"]].append(edge["source"])
    depth = {node_id: 0 for node_id in flow}
    for _ in range(len(flow)):
        changed = False
        for node_id, sources in incoming.items():
            want = max((depth[item] + 1 for item in sources), default=0)
            if want > depth[node_id] and want <= len(flow):
                depth[node_id] = want
                changed = True
        if not changed:
            break
    return depth


def _nearest_free(desired: float, height: float, taken: list[tuple[float, float]]) -> float:
    """The top closest to ``desired`` where a node of ``height`` keeps NODE_GAP to every taken span."""

    def free(top: float) -> bool:
        return all(top + height + NODE_GAP <= start or top >= end + NODE_GAP for start, end in taken)

    candidates = [desired]
    for start, end in taken:
        candidates += [start - NODE_GAP - height, end + NODE_GAP]
    return min((top for top in candidates if free(top)), key=lambda top: (abs(top - desired), top))


def arrange(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """A fresh position for every node, top left at MARGIN."""
    boxes = _boxes(nodes, edges)
    types = {node["id"]: str(node["type"]) for node in nodes}
    order = {node["id"]: index for index, node in enumerate(nodes)}
    flow = [node["id"] for node in nodes if node["type"] in FLOW_TYPES]
    depth = _depths(flow, edges)
    parents: dict[str, list[str]] = {node_id: [] for node_id in flow}
    for edge in edges:
        if edge["target"] in parents and edge["source"] in depth and edge["source"] != edge["target"]:
            parents[edge["target"]].append(edge["source"])

    column: dict[str, int] = {}
    top: dict[str, float] = {}
    spans: dict[int, list[tuple[float, float]]] = {}
    # Flow columns, left to right: each column centred on the nodes that lead into it.
    for index in sorted(set(depth.values())):
        ids = [node_id for node_id in flow if depth[node_id] == index]

        def centre(node_id: str) -> float | None:
            known = [top[item] + boxes[item].height / 2 for item in parents[node_id] if item in top]
            return sum(known) / len(known) if known else None

        ids.sort(key=lambda node_id: (centre(node_id) if centre(node_id) is not None else float("inf"), order[node_id]))
        anchors = [value for value in (centre(node_id) for node_id in ids) if value is not None]
        total = sum(boxes[node_id].height for node_id in ids) + NODE_GAP * (len(ids) - 1)
        y = (sum(anchors) / len(anchors) if anchors else 0.0) - total / 2
        for node_id in ids:
            column[node_id], top[node_id] = index, y
            spans.setdefault(index, []).append((y, y + boxes[node_id].height))
            y += boxes[node_id].height + NODE_GAP

    # Helpers next to the node they serve: one column to its left, at the port they feed.
    wants: list[tuple[int, float, int, str]] = []
    loose: list[str] = []
    for node in nodes:
        if node["type"] not in SUPPORT_TYPES:
            continue
        users = [(edge["target"], edge.get("targetHandle")) for edge in edges if edge["source"] == node["id"] and edge["target"] in top]
        if not users:
            loose.append(node["id"])
            continue
        # A shared helper sits by its leftmost user; the edges to the others run right.
        user, handle = min(users, key=lambda item: (column[item[0]], top[item[0]]))
        centre_y = top[user] + _port_offset(boxes[user], handle)
        wants.append((column[user] - 1, centre_y, order[node["id"]], node["id"]))
    for index, centre_y, _, node_id in sorted(wants):
        height = boxes[node_id].height
        taken = spans.setdefault(index, [])
        y = _nearest_free(centre_y - height / 2, height, taken)
        column[node_id], top[node_id] = index, y
        taken.append((y, y + height))
    # Helpers nobody uses yet wait below the first column.
    first = min(spans, default=0)
    for node_id in loose:
        height = boxes[node_id].height
        taken = spans.setdefault(first, [])
        y = _nearest_free(max((end for _, end in taken), default=0.0) + NODE_GAP, height, taken)
        column[node_id], top[node_id] = first, y
        taken.append((y, y + height))

    # Column widths from what they hold; flow nodes on the left edge, helpers on the right,
    # close to the node they feed.
    width: dict[int, float] = {}
    for node_id, index in column.items():
        width[index] = max(width.get(index, 0.0), boxes[node_id].width)
    left: dict[int, float] = {}
    x = 0.0
    for index in sorted(width):
        left[index] = x
        x += width[index] + COLUMN_GAP
    placed: dict[str, dict[str, float]] = {}
    for node_id, index in column.items():
        offset = 0.0 if types[node_id] in FLOW_TYPES else width[index] - boxes[node_id].width
        placed[node_id] = {"x": left[index] + offset, "y": top[node_id]}
    if not placed:
        return {}
    min_x = min(pos["x"] for pos in placed.values())
    min_y = min(pos["y"] for pos in placed.values())
    return {
        node_id: {"x": _snap(MARGIN + pos["x"] - min_x), "y": _snap(MARGIN + pos["y"] - min_y)}
        for node_id, pos in placed.items()
    }


def _anchor(node: dict[str, Any], edges: list[dict[str, Any]]) -> str | None:
    """The neighbour a new node is placed relative to: the node it serves, else the one before it."""
    if node["type"] in SUPPORT_TYPES:
        return next((edge["target"] for edge in edges if edge["source"] == node["id"]), None)
    return next((edge["source"] for edge in edges if edge["target"] == node["id"]), None) or next(
        (edge["target"] for edge in edges if edge["source"] == node["id"]), None
    )


def _overlaps(a: dict[str, float], box_a: _Box, b: dict[str, float], box_b: _Box) -> bool:
    return (
        a["x"] < b["x"] + box_b.width + NODE_GAP
        and b["x"] < a["x"] + box_a.width + NODE_GAP
        and a["y"] < b["y"] + box_b.height + NODE_GAP
        and b["y"] < a["y"] + box_a.height + NODE_GAP
    )


def layout(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], keep: dict[str, dict[str, float]]) -> None:
    """Set ``position`` on every node. Kept nodes stay where the user put them; a new node goes
    where the fresh layout would put it relative to a kept neighbour, then down to a free spot."""
    fresh = arrange(nodes, edges)
    boxes = _boxes(nodes, edges)
    kept = [node["id"] for node in nodes if node["id"] in keep]
    # Without a kept neighbour, a new node follows the kept ones as a group.
    if kept:
        shift_x = sum(float(keep[node_id].get("x", 0)) - fresh[node_id]["x"] for node_id in kept) / len(kept)
        shift_y = sum(float(keep[node_id].get("y", 0)) - fresh[node_id]["y"] for node_id in kept) / len(kept)
    else:
        shift_x = shift_y = 0.0
    final: dict[str, dict[str, float]] = {node_id: dict(keep[node_id]) for node_id in kept}
    # Flow first, so helpers find the node they serve already placed.
    pending = sorted(
        (node for node in nodes if node["id"] not in final),
        key=lambda node: (node["type"] not in FLOW_TYPES, fresh[node["id"]]["x"], fresh[node["id"]]["y"]),
    )
    for node in pending:
        node_id = node["id"]
        anchor = _anchor(node, edges)
        if kept and anchor in final and anchor in fresh:
            spot = {
                "x": float(final[anchor].get("x", 0)) + fresh[node_id]["x"] - fresh[anchor]["x"],
                "y": float(final[anchor].get("y", 0)) + fresh[node_id]["y"] - fresh[anchor]["y"],
            }
        else:
            spot = {"x": fresh[node_id]["x"] + shift_x, "y": fresh[node_id]["y"] + shift_y}
        if kept:
            for _ in range(400):
                clash = next((other for other, pos in final.items() if _overlaps(spot, boxes[node_id], pos, boxes[other])), None)
                if clash is None:
                    break
                spot["y"] = float(final[clash].get("y", 0)) + boxes[clash].height + NODE_GAP
        final[node_id] = {"x": _snap(spot["x"]), "y": _snap(spot["y"])}
    for node in nodes:
        node["position"] = final[node["id"]]
