"""The architect's draft format and its translation into a network document (entwurf.md, 7).

The model writes nodes with short refs and links as pairs. This module turns that into a
real document: ids, positions, port handles (including ``channel:<agentId>``), initial values
from the catalog, credentials and MCP servers resolved by name. Then it checks the result with
the normal validation plus a few hints of its own.
"""

from __future__ import annotations

import copy
import re
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.common.components import error_texts, node_spec, node_types

FLOW_TYPES = frozenset({"chat_input", "orchestrator", "agent", "router", "end"})
SUPPORT_TYPES = frozenset({"llm", "tool", "mcp", "knowledge"})
DRAFT_KEYS = ("name", "description", "tags", "nodes", "links")
# Names the model may use instead of ids; resolved to the id field.
NAME_ALIASES = {
    "credential": "credentialId",
    "embeddingCredential": "embeddingCredentialId",
    "mcpServer": "mcpServerId",
}
_REVERSE_ALIASES = {target: alias for alias, target in NAME_ALIASES.items()}
# Folders on the user's disk; a cloud model sees them only with "Pfade an Cloud-Modelle" (E-6).
PATH_FIELDS = frozenset({"rootPath", "sourcePath"})
# Shown when reading a network back even if they equal the catalog's initial value.
_ALWAYS_SHOWN = frozenset({"kind", "provider", "model"})
# Server bookkeeping that is no part of a base document.
_SERVER_KEYS = ("knowledge", "version", "revision")
GRID = 16
COLUMN = 320
ROW = 160
SUPPORT_ROW = 112
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,40}$")


@dataclass
class Problem:
    text: str
    ref: str | None = None
    key: str | None = None
    severity: str = "error"  # "error" | "hint"

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"severity": self.severity, "text": self.text}
        if self.ref:
            out["ref"] = self.ref
        if self.key:
            out["key"] = self.key
        return out


@dataclass
class Lookup:
    """What the translation needs from the app; tests pass plain lists."""

    credentials: list[dict[str, Any]] = field(default_factory=list)  # id, name, kind
    mcp_servers: list[dict[str, Any]] = field(default_factory=list)  # id, name, enabled
    # tag_key -> {"tools": bool}; None while Ollama is unreachable.
    installed: dict[str, dict[str, Any]] | None = None
    validate: Callable[[dict[str, Any]], list[tuple[str | None, str]]] | None = None


@dataclass
class Compiled:
    document: dict[str, Any]
    ids: dict[str, str]
    problems: list[Problem]

    @property
    def errors(self) -> list[Problem]:
        return [item for item in self.problems if item.severity == "error"]

    @property
    def hints(self) -> list[Problem]:
        return [item for item in self.problems if item.severity == "hint"]


def empty_draft() -> dict[str, Any]:
    return {"name": "", "description": "", "tags": [], "nodes": [], "links": []}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "branch"


def _snap(value: float) -> int:
    return int(round(value / GRID) * GRID)


# --- normalizing what the model wrote -------------------------------------------------------


def normalize(raw: object) -> tuple[dict[str, Any], list[Problem]]:
    """A clean draft from the model's input; shape problems are reported, not fatal."""
    problems: list[Problem] = []
    draft = empty_draft()
    if not isinstance(raw, dict):
        return draft, [Problem("The draft must be an object with name, nodes and links.")]
    for key in raw:
        if key not in DRAFT_KEYS:
            problems.append(Problem(f"Unknown draft key '{key}'; allowed: {', '.join(DRAFT_KEYS)}."))
    draft["name"] = str(raw.get("name") or "").strip()[:120]
    draft["description"] = str(raw.get("description") or "").strip()[:2000]
    tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
    draft["tags"] = [str(tag).strip()[:40] for tag in tags if str(tag).strip()][:20]
    seen: set[str] = set()
    for item in raw.get("nodes") or []:
        if not isinstance(item, dict):
            problems.append(Problem("Every node must be an object with ref, type and data."))
            continue
        ref = str(item.get("ref") or "").strip()
        node_type = str(item.get("type") or "").strip()
        if not _REF.fullmatch(ref):
            problems.append(Problem(f"Node ref '{ref}' must be a short name (letters, digits, - _ .).", ref=ref or None))
            continue
        if ref in seen:
            problems.append(Problem(f"Node ref '{ref}' is used twice.", ref=ref))
            continue
        if node_spec(node_type) is None:
            types = ", ".join(spec["type"] for spec in node_types())
            problems.append(Problem(f"Unknown node type '{node_type}'; known: {types}.", ref=ref))
            continue
        seen.add(ref)
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        draft["nodes"].append({"ref": ref, "type": node_type, "data": copy.deepcopy(data)})
    for item in raw.get("links") or []:
        link = _link(item)
        if link is None:
            problems.append(Problem(f"A link must be [from, to] or [from, to, kind]; got {item!r}."))
            continue
        if link not in draft["links"]:
            draft["links"].append(link)
    return draft, problems


def _link(item: object) -> list[str] | None:
    if isinstance(item, dict):
        item = [item.get("from"), item.get("to"), item.get("kind")]
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        return None
    parts = [str(part).strip() for part in item[:3] if part is not None and str(part).strip()]
    if len(parts) < 2:
        return None
    return parts


def patch(draft: dict[str, Any], change: dict[str, Any]) -> tuple[dict[str, Any], list[Problem]]:
    """Apply draft_patch: upsert and remove nodes, add and remove links, set the head."""
    problems: list[Problem] = []
    current = copy.deepcopy(draft) if draft else empty_draft()
    for key in ("name", "description", "tags"):
        if key in change:
            current[key] = change[key]
    nodes = {item["ref"]: item for item in current.get("nodes") or []}
    order = [item["ref"] for item in current.get("nodes") or []]
    removed = {str(ref).strip() for ref in change.get("removeNodes") or []}
    for ref in removed:
        if ref not in nodes:
            problems.append(Problem(f"Cannot remove '{ref}': no such node.", ref=ref))
        nodes.pop(ref, None)
    for item in change.get("upsertNodes") or []:
        if not isinstance(item, dict) or not str(item.get("ref") or "").strip():
            problems.append(Problem("upsertNodes entries need a ref."))
            continue
        ref = str(item["ref"]).strip()
        if ref in nodes:
            merged = nodes[ref]
            if item.get("type") and item["type"] != merged["type"]:
                merged["type"] = item["type"]
            data = dict(merged.get("data") or {})
            for key, value in (item.get("data") or {}).items():
                if value is None:
                    data.pop(key, None)
                else:
                    data[key] = value
            merged["data"] = data
        else:
            nodes[ref] = {"ref": ref, "type": item.get("type"), "data": dict(item.get("data") or {})}
            order.append(ref)
    current["nodes"] = [nodes[ref] for ref in order if ref in nodes]
    links = [link for link in current.get("links") or [] if link[0] not in removed and link[1] not in removed]
    drop = [_link(item) for item in change.get("removeLinks") or []]
    for link in drop:
        if link is None:
            continue
        before = len(links)
        links = [item for item in links if item[:2] != link[:2] or (len(link) > 2 and item[2:3] != link[2:3])]
        if len(links) == before:
            problems.append(Problem(f"Cannot remove link {link}: no such link."))
    current["links"] = links + [item for item in change.get("addLinks") or []]
    cleaned, more = normalize(current)
    return cleaned, problems + more


# --- translation ----------------------------------------------------------------------------


def _resolve_named(field_key: str, value: object, lookup: Lookup) -> tuple[str | None, str | None]:
    """Name (or id) of a credential or MCP server -> id, or an error text."""
    text = str(value or "").strip()
    if not text:
        return None, None
    rows = lookup.mcp_servers if field_key == "mcpServerId" else lookup.credentials
    for row in rows:
        if row.get("id") == text:
            return text, None
    lowered = text.lower()
    for row in rows:
        if str(row.get("name") or "").strip().lower() == lowered:
            return str(row["id"]), None
    names = ", ".join(sorted(str(row.get("name")) for row in rows)) or "none set up"
    what = "MCP server" if field_key == "mcpServerId" else "credential"
    return None, f"Unknown {what} '{text}'. Available: {names}."


def _check_value(spec: dict[str, Any], value: Any) -> str | None:
    kind = spec.get("type")
    if kind in {"string", "text"}:
        return None if isinstance(value, str) else "must be text"
    if kind == "boolean":
        return None if isinstance(value, bool) else "must be true or false"
    if kind in {"integer", "number"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "must be a number"
        if kind == "integer" and not float(value).is_integer():
            return "must be a whole number"
        low, high = spec.get("min"), spec.get("max")
        if (low is not None and value < low) or (high is not None and value > high):
            return f"must be between {low if low is not None else '-inf'} and {high if high is not None else 'inf'}"
        return None
    if kind == "enum":
        return None if value in (spec.get("values") or []) else f"must be one of {', '.join(spec.get('values') or [])}"
    if kind == "string[]":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return "must be a list of texts"
        allowed = spec.get("values")
        if allowed and any(item not in allowed for item in value):
            return f"entries must be from {', '.join(allowed)}"
        return None
    if kind == "object[]":
        return None if isinstance(value, list) and all(isinstance(item, dict) for item in value) else "must be a list of objects"
    return None


def _branches(raw: list[dict[str, Any]], problems: list[Problem], ref: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    used: set[str] = set()
    for item in raw:
        name = str(item.get("name") or "").strip()
        branch_id = str(item.get("id") or "").strip() or f"br-{_slug(name)}"
        while branch_id in used or branch_id == "default":
            branch_id = f"{branch_id}-{len(used) + 1}"
        used.add(branch_id)
        match = item.get("match") or "contains"
        if match not in {"contains", "startsWith", "firstLine", "regex"}:
            problems.append(Problem(f"Branch '{name}': match must be contains, startsWith, firstLine or regex.", ref=ref))
            match = "contains"
        out.append({"id": branch_id, "name": name, "match": match, "pattern": str(item.get("pattern") or "")})
    return out


def _node_data(
    node: dict[str, Any], lookup: Lookup, problems: list[Problem], start: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Catalog initial values (or ``start``, the stored data of a read-in node) plus the draft's data."""
    spec = node_spec(node["type"]) or {"fields": []}
    fields = {item["key"]: item for item in spec["fields"]}
    ref = node["ref"]
    data: dict[str, Any] = {}
    if start is not None:
        data = copy.deepcopy(start)
    else:
        for item in spec["fields"]:
            if "initial" in item:
                data[item["key"]] = copy.deepcopy(item["initial"])
    given = dict(node.get("data") or {})
    kind = given.get("kind", data.get("kind"))
    for key, value in given.items():
        target = NAME_ALIASES.get(key, key)
        if target not in fields:
            problems.append(Problem(f"'{ref}' ({node['type']}) has no field '{key}'.", ref=ref))
            continue
        field_spec = fields[target]
        if node["type"] == "tool" and field_spec.get("kinds") and kind not in field_spec["kinds"]:
            problems.append(
                Problem(f"'{ref}': field '{target}' does nothing for tool kind '{kind}'; left out.", ref=ref, severity="hint")
            )
            continue
        if value is None:
            data.pop(target, None)
            continue
        if target in {"credentialId", "embeddingCredentialId", "mcpServerId"}:
            resolved, error = _resolve_named(target, value, lookup)
            if error:
                problems.append(Problem(f"'{ref}': {error}", ref=ref))
                continue
            if resolved:
                data[target] = resolved
            continue
        error = _check_value(field_spec, value)
        if error:
            problems.append(Problem(f"'{ref}': {target} {error}.", ref=ref))
            continue
        data[target] = copy.deepcopy(value)
    if node["type"] == "router":
        data["branches"] = _branches(list(data.get("branches") or []), problems, ref)
    return data


def _handles(src: dict[str, Any], dst: dict[str, Any], kind: str | None) -> tuple[str, str] | str:
    """(sourceHandle, targetHandle) for a link, or an error text."""
    s, d = src["type"], dst["type"]
    if s == "llm" and d in {"agent", "orchestrator"}:
        return "llm", "llm"
    if s in {"tool", "mcp"} and d in {"agent", "orchestrator"}:
        return "tool", "tool"
    if s == "knowledge" and d == "agent":
        return "knowledge", "knowledge"
    if s == "orchestrator" and d == "agent":
        return f"channel:{dst['id']}", "channel"
    if s == "orchestrator" and d in {"end", "router"}:
        return "message", "message"
    if s == "chat_input" and d in {"agent", "orchestrator", "router", "end"}:
        return "message", "message"
    if s == "agent" and d in {"agent", "router", "end"}:
        return ("handoff" if kind == "handoff" else "message"), "message"
    if s == "router" and d in {"agent", "router", "end"}:
        branches = src["data"].get("branches") or []
        if kind in (None, "", "default"):
            if kind is None and branches:
                names = ", ".join(str(item["name"]) for item in branches)
                return f"a link from router '{src['ref']}' needs a branch name ({names}) or 'default' as third entry"
            return "default", "message"
        for branch in branches:
            if kind in (branch["name"], branch["id"]):
                return branch["id"], "message"
        names = ", ".join(str(item["name"]) for item in branches)
        return f"router '{src['ref']}' has no branch '{kind}' ({names}, default)"
    return f"{s} cannot connect to {d}"


def _layout(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], keep: dict[str, dict[str, float]]) -> None:
    """Columns from left to right along the flow; models, tools and knowledge below their user."""
    flow =[node for node in nodes if node["type"] in FLOW_TYPES]
    incoming: dict[str, list[str]] = {node["id"]: [] for node in flow}
    for edge in edges:
        if edge["source"] in incoming and edge["target"] in incoming:
            incoming[edge["target"]].append(edge["source"])
    depth: dict[str, int] = {node["id"]: 0 for node in flow}
    for _ in range(len(flow)):
        changed = False
        for node_id, sources in incoming.items():
            want = max((depth[item] + 1 for item in sources), default=0)
            if want > depth[node_id] and want <= len(flow):
                depth[node_id] = want
                changed = True
        if not changed:
            break
    # Ends close the flow: always the last column, whatever leads to them.
    last = max((depth[node["id"]] for node in flow if node["type"] != "end"), default=-1) + 1
    for node in flow:
        if node["type"] == "end":
            depth[node["id"]] = max(depth[node["id"]], last)
    columns: dict[int, list[str]] = {}
    for node in flow:
        columns.setdefault(depth[node["id"]], []).append(node["id"])
    placed: dict[str, dict[str, float]] = {}
    for column, ids in columns.items():
        for row, node_id in enumerate(ids):
            placed[node_id] = {"x": _snap(64 + column * COLUMN), "y": _snap(64 + row * ROW)}
    bottom = max((pos["y"] for pos in placed.values()), default=64) + ROW + SUPPORT_ROW
    stacked: dict[int, int] = {}
    for node in nodes:
        if node["type"] not in SUPPORT_TYPES:
            continue
        user = next((edge["target"] for edge in edges if edge["source"] == node["id"] and edge["target"] in placed), None)
        x = placed[user]["x"] if user else 64
        row = stacked.get(x, 0)
        stacked[x] = row + 1
        placed[node["id"]] = {"x": x, "y": _snap(bottom + row * SUPPORT_ROW)}
    # Kept nodes stay where the user put them; new ones go to a free spot nearby (entwurf.md, 7.3).
    taken = [keep[node["id"]] for node in nodes if node["id"] in keep]
    for node in nodes:
        if node["id"] in keep:
            node["position"] = dict(keep[node["id"]])
            continue
        spot = dict(placed.get(node["id"]) or {"x": 64, "y": 64})
        if taken:
            spot = _free_spot(spot, taken)
        taken.append(spot)
        node["position"] = spot


def _free_spot(spot: dict[str, float], taken: list[dict[str, float]]) -> dict[str, float]:
    """Move a new node down until it overlaps no other node."""
    x, y = float(spot.get("x", 64)), float(spot.get("y", 64))

    def clashes(top: float) -> bool:
        return any(
            abs(float(other.get("x", 0)) - x) < COLUMN * 0.8 and abs(float(other.get("y", 0)) - top) < ROW * 0.75
            for other in taken
        )

    for _ in range(200):
        if not clashes(y):
            break
        y += ROW / 2
    return {"x": _snap(x), "y": _snap(y)}


def compile_draft(
    draft: dict[str, Any],
    lookup: Lookup,
    *,
    ids: dict[str, str] | None = None,
    keep_positions: dict[str, dict[str, float]] | None = None,
    base: dict[str, Any] | None = None,
) -> Compiled:
    """The network document of a draft, with every problem found on the way and by validation.

    ``ids`` keeps node ids stable across changes (ref -> id) and is updated with new refs.
    ``base`` is a network read in (entwurf.md, 7.3): its top-level fields carry over, and nodes it
    already has keep their stored data (fields the draft leaves out stay), position and extra keys;
    edges it already has keep their ids.
    """
    clean, problems = normalize(draft)
    ref_ids = dict(ids or {})
    base_nodes = {str(node.get("id")): node for node in (base or {}).get("nodes") or []}
    base_edges = {
        (edge.get("source"), edge.get("sourceHandle"), edge.get("target"), edge.get("targetHandle")): edge
        for edge in (base or {}).get("edges") or []
    }
    keep = {node_id: dict(node["position"]) for node_id, node in base_nodes.items() if isinstance(node.get("position"), dict)}
    keep.update(keep_positions or {})
    nodes: list[dict[str, Any]] = []
    for item in clean["nodes"]:
        node_id = ref_ids.get(item["ref"]) or _new_id(item["type"])
        ref_ids[item["ref"]] = node_id
        prior = base_nodes.get(node_id)
        same = prior is not None and prior.get("type") == item["type"]
        node = {"id": node_id, "type": item["type"], "ref": item["ref"]}
        node["data"] = _node_data(item, lookup, problems, start=dict(prior.get("data") or {}) if same else None)
        node["extra"] = {key: value for key, value in (prior or {}).items() if key not in {"id", "type", "position", "data"}}
        nodes.append(node)
    by_ref = {node["ref"]: node for node in nodes}
    edges: list[dict[str, Any]] = []
    for link in clean["links"]:
        src, dst = by_ref.get(link[0]), by_ref.get(link[1])
        if src is None or dst is None:
            missing = link[0] if src is None else link[1]
            problems.append(Problem(f"Link {link}: no node '{missing}'.", ref=missing))
            continue
        handles = _handles(src, dst, link[2] if len(link) > 2 else None)
        if isinstance(handles, str):
            problems.append(Problem(f"Link {link}: {handles}.", ref=src["ref"]))
            continue
        prior_edge = base_edges.get((src["id"], handles[0], dst["id"], handles[1]))
        if prior_edge is not None:
            edges.append(copy.deepcopy(prior_edge))
            continue
        edges.append(
            {
                "id": _new_id("e"),
                "source": src["id"],
                "sourceHandle": handles[0],
                "target": dst["id"],
                "targetHandle": handles[1],
            }
        )
    _layout(nodes, edges, keep)
    document = {key: value for key, value in (base or {}).items() if key not in _SERVER_KEYS}
    document.update(
        {
            "schemaVersion": 1,
            "name": clean["name"],
            "description": clean["description"],
            "tags": clean["tags"],
            "nodes": [
                {**copy.deepcopy(node["extra"]), **{key: node[key] for key in ("id", "type", "position", "data")}}
                for node in nodes
            ],
            "edges": edges,
        }
    )
    compiled = Compiled(document=document, ids=ref_ids, problems=problems)
    compiled.problems.extend(check(document, lookup, {node["id"]: node["ref"] for node in nodes}))
    return compiled


def check(document: dict[str, Any], lookup: Lookup, refs: dict[str, str]) -> list[Problem]:
    """Validation errors of the document plus the architect's hints."""
    problems: list[Problem] = []
    if not document.get("name"):
        problems.append(Problem("The network needs a name."))
    texts = error_texts()
    if lookup.validate is not None:
        for node_id, key in lookup.validate(document):
            problems.append(Problem(texts.get(key, key), ref=refs.get(node_id or "", None), key=key))
    nodes = {node["id"]: node for node in document.get("nodes") or []}
    has_tools = {
        edge["target"] for edge in document.get("edges") or [] if edge.get("targetHandle") == "tool"
    }
    for node in nodes.values():
        data = node.get("data") or {}
        ref = refs.get(node["id"])
        if node["type"] == "llm" and data.get("provider", "ollama") == "ollama" and lookup.installed is not None:
            model = str(data.get("model") or "").strip()
            info = lookup.installed.get(model.lower().removesuffix(":latest")) if model else None
            if model and info is None:
                problems.append(Problem(f"'{ref}': model {model} is not installed.", ref=ref, severity="hint"))
            elif info is not None and not info.get("tools"):
                users = [
                    edge["target"]
                    for edge in document.get("edges") or []
                    if edge["source"] == node["id"] and edge["target"] in has_tools
                ]
                if users:
                    problems.append(
                        Problem(f"'{ref}': {model} cannot call tools, but it drives nodes with tools.", ref=ref, severity="hint")
                    )
        if node["type"] == "tool":
            # Risks carry a key; the closing dialog lists them (entwurf.md, 3 step 7).
            if data.get("kind") == "terminal" and data.get("terminalMode") == "unrestricted":
                problems.append(
                    Problem(f"'{ref}': unrestricted terminal runs any command; justify it to the user.", ref=ref, key="risk.terminal", severity="hint")
                )
            if data.get("kind") == "file_access" and data.get("allowDelete"):
                problems.append(
                    Problem(f"'{ref}': file access may delete files; justify it to the user.", ref=ref, key="risk.fileDelete", severity="hint")
                )
            if data.get("kind") == "http" and data.get("credentialId"):
                problems.append(
                    Problem(f"'{ref}': HTTP sends a credential to {data.get('url') or 'its URL'}.", ref=ref, key="risk.httpCredential", severity="hint")
                )
    return problems


def report(compiled: Compiled, *, max_items: int = 30) -> dict[str, Any]:
    """What a draft tool returns to the model: ok, errors, hints."""
    errors = [item.as_dict() for item in compiled.errors][:max_items]
    hints = [item.as_dict() for item in compiled.hints][:max_items]
    return {
        "ok": not compiled.errors,
        "nodes": len(compiled.document.get("nodes") or []),
        "edges": len(compiled.document.get("edges") or []),
        "errors": errors,
        "hints": hints,
    }


# --- reading a stored network back (entwurf.md, 7.3) -------------------------------------------


@dataclass
class Decompiled:
    draft: dict[str, Any]
    # ref -> node id of ``base``.
    ids: dict[str, str]
    # The document compiling builds on: the stored network, or a copy with new ids for a template.
    base: dict[str, Any]
    # ref -> fields left out because a cloud model may not see them; their values stay in ``base``.
    hidden: dict[str, list[str]]


def _ref_text(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.replace("ß", "ss"))
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", plain).strip("-._")[:36]


def _ref_for(node: dict[str, Any], lookup: Lookup, used: set[str]) -> str:
    data = node.get("data") or {}
    node_type = str(node.get("type") or "node")
    label = str(data.get("displayName") or "").strip()
    if not label:
        if node_type == "llm":
            label = str(data.get("model") or "llm").split("/")[-1].split(":")[0]
        elif node_type == "tool":
            label = str(data.get("kind") or "tool")
        elif node_type == "mcp":
            server = next((row for row in lookup.mcp_servers if row.get("id") == data.get("mcpServerId")), None)
            label = str((server or {}).get("name") or "mcp")
        elif node_type == "chat_input":
            label = "chat"
        else:
            label = node_type
    base = _ref_text(label) or _ref_text(node_type) or "node"
    if not base[0].isalnum():
        base = f"n{base}"[:36]
    ref, count = base, 2
    while ref.lower() in used:
        ref = f"{base}-{count}"
        count += 1
    used.add(ref.lower())
    return ref


def _name_of(field_key: str, value: object, lookup: Lookup) -> str | None:
    rows = lookup.mcp_servers if field_key == "mcpServerId" else lookup.credentials
    row = next((item for item in rows if item.get("id") == value), None)
    return str(row["name"]) if row and row.get("name") else None


def _draft_data(node: dict[str, Any], lookup: Lookup, hide_paths: bool) -> tuple[dict[str, Any], list[str]]:
    """The fields worth showing: set and different from the catalog's initial value."""
    spec = node_spec(str(node.get("type"))) or {"fields": []}
    fields = {item["key"]: item for item in spec["fields"]}
    data = node.get("data") or {}
    kind = data.get("kind")
    out: dict[str, Any] = {}
    hidden: list[str] = []
    for key, value in data.items():
        field_spec = fields.get(key)
        if field_spec is None:
            continue  # unknown here; it stays in the base document
        if node.get("type") == "tool" and field_spec.get("kinds") and kind not in field_spec["kinds"]:
            continue
        if key not in _ALWAYS_SHOWN:
            if "initial" in field_spec and value == field_spec["initial"]:
                continue
            if value is None or value == "" or value == []:
                continue
        if key in PATH_FIELDS and hide_paths and value:
            hidden.append(key)
            continue
        if key in _REVERSE_ALIASES:
            out[_REVERSE_ALIASES[key]] = _name_of(key, value, lookup) or value
            continue
        out[key] = copy.deepcopy(value)
    return out, hidden


def _link_of(edge: dict[str, Any], nodes: dict[str, dict[str, Any]], refs: dict[str, str]) -> list[str] | None:
    src, dst = nodes.get(str(edge.get("source"))), nodes.get(str(edge.get("target")))
    if src is None or dst is None:
        return None
    link = [refs[src["id"]], refs[dst["id"]]]
    handle = str(edge.get("sourceHandle") or "")
    if src.get("type") == "router":
        if handle == "default":
            link.append("default")
        else:
            branches = (src.get("data") or {}).get("branches") or []
            branch = next((item for item in branches if item.get("id") == handle), None)
            names = [str(item.get("name") or "") for item in branches]
            name = str((branch or {}).get("name") or "")
            link.append(name if name and names.count(name) == 1 else handle)
    elif src.get("type") == "agent" and handle == "handoff":
        link.append("handoff")
    return link


def _fresh_copy(document: dict[str, Any]) -> dict[str, Any]:
    """A template: the same network under new node and edge ids, without its own id."""
    mapping = {str(node.get("id")): _new_id(str(node.get("type") or "node")) for node in document.get("nodes") or []}
    nodes = []
    for node in document.get("nodes") or []:
        copied = copy.deepcopy(node)
        copied["id"] = mapping[str(node.get("id"))]
        nodes.append(copied)
    edges = []
    for edge in document.get("edges") or []:
        copied = copy.deepcopy(edge)
        copied["id"] = _new_id("e")
        copied["source"] = mapping.get(str(edge.get("source")), edge.get("source"))
        copied["target"] = mapping.get(str(edge.get("target")), edge.get("target"))
        handle = str(edge.get("sourceHandle") or "")
        if handle.startswith("channel:"):
            copied["sourceHandle"] = f"channel:{mapping.get(handle.split(':', 1)[1], handle.split(':', 1)[1])}"
        edges.append(copied)
    out = {key: value for key, value in document.items() if key not in {"id", "isActive", "updatedAt", *_SERVER_KEYS}}
    out["nodes"] = nodes
    out["edges"] = edges
    return out


def decompile(
    document: dict[str, Any], lookup: Lookup, *, hide_paths: bool = False, template: bool = False
) -> Decompiled:
    """A stored network as a draft. Compiling that draft with ``base`` gives the same document back."""
    base = _fresh_copy(document) if template else {
        key: copy.deepcopy(value) for key, value in document.items() if key not in _SERVER_KEYS
    }
    used: set[str] = set()
    refs: dict[str, str] = {}
    nodes = {str(node.get("id")): node for node in base.get("nodes") or []}
    draft_nodes: list[dict[str, Any]] = []
    hidden: dict[str, list[str]] = {}
    for node in base.get("nodes") or []:
        ref = _ref_for(node, lookup, used)
        refs[str(node["id"])] = ref
        data, left_out = _draft_data(node, lookup, hide_paths)
        if left_out:
            hidden[ref] = left_out
        draft_nodes.append({"ref": ref, "type": node.get("type"), "data": data})
    links = [link for link in (_link_of(edge, nodes, refs) for edge in base.get("edges") or []) if link]
    draft = {
        "name": str(base.get("name") or ""),
        "description": str(base.get("description") or ""),
        "tags": list(base.get("tags") or []),
        "nodes": draft_nodes,
        "links": links,
    }
    return Decompiled(draft=draft, ids={ref: node_id for node_id, ref in refs.items()}, base=base, hidden=hidden)
