"""The architect's tools (fix/netz-architekt/entwurf.md, 8).

Each tool returns JSON text for the model and a short line for the chat. None of them writes a
network; creating and changing go through the closing dialog the user confirms (T2).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.architect import catalog_view
from app.architect.draft import Lookup, compile_draft, normalize, patch, report
from app.db.architect import ArchitectSessionRow

log = logging.getLogger("agentus.architect")

BRIEF_FIELDS = ("goal", "input", "output", "sources", "deployment", "tools", "constraints")
_TEXT_LIMIT = 12_000


@dataclass
class ToolContext:
    session: ArchitectSessionRow
    cloud: bool
    lookup: Callable[[], Lookup]
    send_paths: bool = False
    # What the call changed: "brief", "draft", "proposal". The loop sends the new state then.
    changed: set[str] = field(default_factory=set)


@dataclass
class ToolResult:
    content: str
    # Line for the chat: an i18n key (architect.tool.*) and its values.
    key: str
    params: dict[str, Any] = field(default_factory=dict)
    ok: bool = True


@dataclass
class ArchitectTool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[[ToolContext, dict[str, Any]], ToolResult]


def _json(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= _TEXT_LIMIT else text[:_TEXT_LIMIT] + "…(cut)"


def _object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


# --- brief ------------------------------------------------------------------------------------


def _set_brief(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    brief = dict(ctx.session.brief or {})
    touched = []
    for key in BRIEF_FIELDS:
        if key in args:
            value = str(args[key] or "").strip()[:1000]
            if value:
                brief[key] = value
            else:
                brief.pop(key, None)
            touched.append(key)
    ctx.session.brief = brief
    ctx.changed.add("brief")
    return ToolResult(_json({"brief": brief}), "architect.tool.brief", {"count": len(touched)})


# --- catalog ----------------------------------------------------------------------------------


def _list_components(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    servers = [
        {"name": item["name"], "enabled": item["enabled"], "tools": len(item["tools"])}
        for item in catalog_view.mcp_servers()
    ]
    return ToolResult(
        _json({"components": catalog_view.overview_lines(), "mcpServers": servers}),
        "architect.tool.components",
    )


def _describe(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name") or "")
    found = catalog_view.describe(name)
    if found is None:
        return ToolResult(_json({"error": f"Nothing named '{name}'. Use list_components."}), "architect.tool.unknown", {"name": name}, ok=False)
    return ToolResult(_json(found), "architect.tool.describe", {"name": name})


def _guide(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    pattern = str(args.get("pattern") or "")
    text = catalog_view.guide(pattern)
    if text is None:
        return ToolResult(_json({"error": f"No guide '{pattern}'. Guides: {', '.join(catalog_view.GUIDES)}."}), "architect.tool.guideMissing", {"name": pattern}, ok=False)
    return ToolResult(text, "architect.tool.guide", {"name": pattern})


# --- environment --------------------------------------------------------------------------------


def _gpus() -> list[dict[str, Any]]:
    try:
        from app.run.resources import latest

        snap = latest()
    except Exception:
        return []
    return [
        {"name": gpu.name, "vramTotalGB": round(gpu.vram_total_bytes / 1e9, 1), "vramUsedGB": round(gpu.vram_used_bytes / 1e9, 1)}
        for gpu in snap.gpus or []
        if gpu.inference
    ]


def _parameters_b(raw: str | None) -> float | None:
    text = (raw or "").strip().upper()
    if not text:
        return None
    try:
        if text.endswith("B"):
            return float(text[:-1])
        if text.endswith("M"):
            return float(text[:-1]) / 1000
    except ValueError:
        return None
    return None


def _list_models(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    from app.llm.catalog import list_installed

    installed = list_installed()
    if installed.message_key:
        return ToolResult(_json({"error": "Ollama is not reachable; no local models known."}), "architect.tool.ollamaDown", ok=False)
    vram = sum(gpu["vramTotalGB"] for gpu in _gpus())
    rows = []
    for item in installed.items:
        size = round((item.size_bytes or 0) / 1e9, 1)
        rows.append(
            {
                "name": item.name,
                "kind": item.kind,
                "parameters": item.parameter_size,
                "context": item.context_length,
                "tools": item.tools,
                "thinking": item.thinking,
                "vision": item.vision,
                "sizeGB": size,
                "fitsGpu": (size * 1.15 <= vram) if vram else None,
            }
        )
    return ToolResult(_json({"models": rows, "gpuVramGB": vram}), "architect.tool.models", {"count": len(rows)})


def _environment(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    from app.db.credentials import list_credentials
    from app.settings.service import is_run_busy

    credentials = [{"name": row["name"], "kind": row["kind"]} for row in list_credentials()]
    return ToolResult(
        _json(
            {
                "credentials": credentials,
                "gpus": _gpus(),
                "networkRunning": is_run_busy(),
                "cloudSession": ctx.cloud,
            }
        ),
        "architect.tool.environment",
    )


# --- library --------------------------------------------------------------------------------------


def _matches(text: str, query: str) -> bool:
    words = [word for word in query.lower().split() if word]
    low = text.lower()
    return all(word in low for word in words)


def _list_prompts(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    from app.prompts.service import list_items

    query = str(args.get("query") or "")
    rows = [
        {"id": item["id"], "name": item["name"], "description": item["description"], "tags": item["tags"]}
        for item in list_items()
        if not query or _matches(f"{item['name']} {item['description']} {' '.join(item['tags'])}", query)
    ]
    return ToolResult(_json({"prompts": rows[:50]}), "architect.tool.prompts", {"count": len(rows)})


def _get_prompt(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    from app.http.errors import AppError
    from app.prompts.service import get_item

    try:
        item = get_item(str(args.get("id") or ""))
    except AppError:
        return ToolResult(_json({"error": "No such prompt."}), "architect.tool.promptMissing", ok=False)
    return ToolResult(_json({"name": item["name"], "body": item.get("body", "")}), "architect.tool.prompt", {"name": item["name"]})


def _list_networks(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    from app.networks.service import list_network_items

    query = str(args.get("query") or "")
    rows = []
    for item in list_network_items():
        text = f"{item['name']} {item.get('description') or ''} {' '.join(item.get('tags') or [])}"
        if query and not _matches(text, query):
            continue
        rows.append(
            {
                "id": item["id"],
                "name": item["name"],
                "kind": item.get("kind"),
                "tags": item.get("tags") or [],
                "description": item.get("description") or "",
                "valid": item.get("validationStatus") == "valid",
            }
        )
    return ToolResult(_json({"networks": rows[:50]}), "architect.tool.networks", {"count": len(rows)})


# --- draft ------------------------------------------------------------------------------------------


def session_base(session: ArchitectSessionRow) -> dict[str, Any] | None:
    """The network read in (entwurf.md, 7.3): compiling builds on it."""
    base = (session.source or {}).get("base")
    return base if isinstance(base, dict) else None


def compile_for(session: ArchitectSessionRow, lookup: Lookup, draft: dict[str, Any] | None = None):
    """The session's draft (or ``draft``) as a document, on top of the network read in."""
    return compile_draft(draft if draft is not None else session.draft or {}, lookup, ids=session.ids, base=session_base(session))


def apply_draft(ctx: ToolContext, draft: dict[str, Any]) -> dict[str, Any]:
    """Store the draft in the session and return the check for the model."""
    compiled = compile_for(ctx.session, ctx.lookup(), draft)
    clean, _ = normalize(draft)
    ctx.session.draft = clean
    ctx.session.ids = {ref: node_id for ref, node_id in compiled.ids.items() if any(n["ref"] == ref for n in clean["nodes"])}
    ctx.changed.add("draft")
    return report(compiled)


def _draft_set(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    result = apply_draft(ctx, args.get("draft") if isinstance(args.get("draft"), dict) else args)
    return ToolResult(_json(result), *_draft_summary(result))


def _draft_patch(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    merged, problems = patch(ctx.session.draft or {}, args)
    result = apply_draft(ctx, merged)
    if problems:
        result["patchProblems"] = [item.as_dict() for item in problems]
    return ToolResult(_json(result), *_draft_summary(result))


def _draft_summary(result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    params = {"nodes": result["nodes"], "edges": result["edges"], "count": len(result["errors"])}
    return ("architect.tool.draftValid" if result["ok"] else "architect.tool.draftErrors"), params


# --- registry ----------------------------------------------------------------------------------------

_NODE_SCHEMA = {
    "type": "object",
    "properties": {
        "ref": {"type": "string", "description": "Short unique name, for example chat, chief, coder, llm_main."},
        "type": {"type": "string", "description": "Node type from list_components."},
        "data": {"type": "object", "description": "Fields from describe_component. Credentials and MCP servers by name: credential, embeddingCredential, mcpServer."},
    },
    "required": ["ref", "type"],
}
_LINK_SCHEMA = {
    "type": "array",
    "items": {"type": "string"},
    "description": "[from_ref, to_ref] or [from_ref, to_ref, kind]; kind is a router branch name, 'default' or 'handoff'.",
}


def base_tools() -> list[ArchitectTool]:
    return [
        ArchitectTool(
            "set_brief",
            "Record or update the brief (Steckbrief): what the network is for. Fill it before drafting. Empty text clears a field.",
            _object({key: {"type": "string"} for key in BRIEF_FIELDS}),
            _set_brief,
        ),
        ArchitectTool("list_components", "One line per node type and tool kind, plus the MCP servers set up.", _object({}), _list_components),
        ArchitectTool(
            "describe_component",
            "Fields, defaults, ranges, ports, rules and tips of a node type (agent, llm, …), a tool kind (web_search, terminal, …) or an MCP server name.",
            _object({"name": {"type": "string"}}, ["name"]),
            _describe,
        ),
        ArchitectTool(
            "get_guide",
            "A building guide with structure, rules and prompt templates: 'linear' (a chain of agents), 'orchestrator' "
            "(a chief with agents), 'knowledge' (questions about the user's documents) or 'router' (triage into paths).",
            _object({"pattern": {"type": "string", "enum": list(catalog_view.GUIDES)}}, ["pattern"]),
            _guide,
        ),
        ArchitectTool("list_models", "Installed local models with size, context, capabilities and GPU fit.", _object({}), _list_models),
        ArchitectTool("environment", "Credentials (names only), GPUs, whether a network runs, whether this is a cloud session.", _object({}), _environment),
        ArchitectTool("list_prompts", "Prompts in the user's library; optional search words.", _object({"query": {"type": "string"}}), _list_prompts),
        ArchitectTool("get_prompt", "The text of a library prompt by id.", _object({"id": {"type": "string"}}, ["id"]), _get_prompt),
        ArchitectTool(
            "list_networks",
            "The user's networks: name, kind, tags, description, valid. Their content is not included.",
            _object({"query": {"type": "string"}}),
            _list_networks,
        ),
        ArchitectTool(
            "draft_set",
            "Replace the whole draft. Returns ok, errors and hints of the check; fix errors with draft_patch.",
            _object(
                {
                    "draft": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "nodes": {"type": "array", "items": _NODE_SCHEMA},
                            "links": {"type": "array", "items": _LINK_SCHEMA},
                        },
                        "required": ["name", "nodes", "links"],
                    }
                },
                ["draft"],
            ),
            _draft_set,
        ),
        ArchitectTool(
            "draft_patch",
            "Change parts of the draft: upsertNodes (merge data by ref; null removes a field), removeNodes, addLinks, removeLinks, name, description, tags. Returns the check.",
            {
                "type": "object",
                "properties": {
                    "upsertNodes": {"type": "array", "items": _NODE_SCHEMA},
                    "removeNodes": {"type": "array", "items": {"type": "string"}},
                    "addLinks": {"type": "array", "items": _LINK_SCHEMA},
                    "removeLinks": {"type": "array", "items": _LINK_SCHEMA},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "additionalProperties": False,
            },
            _draft_patch,
        ),
    ]


def schemas(tools: list[ArchitectTool]) -> list[dict[str, Any]]:
    return [
        {"type": "function", "function": {"name": tool.name, "description": tool.description, "parameters": tool.parameters}}
        for tool in tools
    ]


def run_tool(tools: list[ArchitectTool], ctx: ToolContext, name: str, raw_args: str) -> ToolResult:
    tool = next((item for item in tools if item.name == name), None)
    if tool is None:
        return ToolResult(_json({"error": f"Unknown tool '{name}'."}), "architect.tool.unknown", {"name": name}, ok=False)
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return ToolResult(_json({"error": "Arguments are not valid JSON."}), "architect.tool.badArgs", {"name": name}, ok=False)
    if not isinstance(args, dict):
        return ToolResult(_json({"error": "Arguments must be an object."}), "architect.tool.badArgs", {"name": name}, ok=False)
    try:
        return tool.run(ctx, args)
    except Exception as exc:  # a tool must not end the turn
        log.warning("architect tool %s failed", name, exc_info=True)
        return ToolResult(_json({"error": f"{name} failed: {type(exc).__name__}"}), "architect.tool.failed", {"name": name}, ok=False)


def app_lookup() -> Lookup:
    """Credentials, MCP servers, installed models and the validation of the running app."""
    from app.db.credentials import list_credentials
    from app.db.engine import get_bootstrap
    from app.llm.catalog import list_installed
    from app.run.graph_models import AgentNetworkDocument
    from app.run.mcp_bridge import validation_kwargs
    from app.run.validate import validate_document
    from app.runtime.ollama import tag_key

    installed = list_installed()
    models = None if installed.message_key else {tag_key(item.name): {"tools": item.tools} for item in installed.items}

    def validate(document: dict[str, Any]) -> list[tuple[str | None, str]]:
        doc = AgentNetworkDocument.model_validate(document)
        errors = validate_document(doc, data_dir=str(get_bootstrap().data_dir), **validation_kwargs())
        return [(error.node_id, error.message_key) for error in errors]

    return Lookup(
        credentials=[{"id": row["id"], "name": row["name"], "kind": row["kind"]} for row in list_credentials()],
        mcp_servers=catalog_view.mcp_servers(),
        installed=models,
        validate=validate,
    )
