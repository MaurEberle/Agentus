from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.common.types import NEEDS_CREDENTIAL, PROVIDERS
from app.db.paths import RAG_DIR_NAME
from app.run.channels import agent_id_from_channel, normalize_channel_edges
from app.run.graph_models import AgentNetworkDocument, GraphEdge, GraphNode
from app.run.models import ValidationError
from app.tools.file_access_tool import is_forbidden_root
from app.tools.kinds import FIRST_PARTY_KINDS

_OUT_HANDLES = {
    "chat_input": {"message"},
    "llm": {"llm"},
    "agent": {"message", "handoff"},
    "tool": {"tool"},
    "knowledge": {"knowledge"},
    "end": set(),
}
_IN_HANDLES = {
    "agent": {"message", "llm", "tool", "knowledge", "channel"},
    "orchestrator": {"message", "llm"},
    "router": {"message"},
    "end": {"message"},
}


def _orchestrator_edge_ok(edge: GraphEdge, dst: GraphNode) -> bool:
    if edge.source_handle == "message":
        return dst.type in {"end", "router"} and edge.target_handle == "message"
    agent_id = agent_id_from_channel(edge.source_handle)
    return (
        agent_id == dst.id
        and dst.type == "agent"
        and edge.target_handle == "channel"
    )


def _err(key: str, node_id: str | None = None) -> ValidationError:
    return ValidationError(node_id=node_id, message_key=key)


def _has_cycle(doc: AgentNetworkDocument) -> bool:
    outgoing: dict[str, list[str]] = {node.id: [] for node in doc.nodes}
    for edge in doc.edges:
        if edge.source in outgoing:
            outgoing[edge.source].append(edge.target)
    visiting: set[str] = set()
    seen: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in seen:
            return False
        visiting.add(node_id)
        for nxt in outgoing.get(node_id, []):
            if visit(nxt):
                return True
        visiting.discard(node_id)
        seen.add(node_id)
        return False

    return any(visit(node.id) for node in doc.nodes)


def _path_ok(source_path: str, data_dir: str) -> bool:
    """Absolute folder, not a drive root, not the help corpus. data_dir is unused."""
    del data_dir
    raw = source_path.strip()
    if not raw:
        return False
    raw = os.path.expanduser(raw)
    if not os.path.isabs(raw):
        return False
    try:
        real = os.path.realpath(os.path.normpath(raw))
    except (ValueError, OSError):
        return False
    if is_forbidden_root(Path(real)):
        return False
    parts = real.replace("\\", "/").split("/")
    if RAG_DIR_NAME in parts:
        return False
    return True


def validate_document(
    doc: AgentNetworkDocument,
    *,
    data_dir: str,
    mcp_enabled: Callable[[str], bool] | None = None,
    mcp_root: Callable[[str], str | None] | None = None,
    mcp_available: bool = True,
) -> list[ValidationError]:
    doc = normalize_channel_edges(doc)
    errors: list[ValidationError] = []
    if not doc.nodes:
        errors.append(_err("graph.end.missing"))
        return errors
    if doc.schema_version != 1:
        errors.append(_err("graph.cycle") if False else _err("run.invalidNetwork"))
    ids = [n.id for n in doc.nodes]
    if len(ids) != len(set(ids)):
        errors.append(_err("run.invalidNetwork"))
    by_id = {n.id: n for n in doc.nodes}
    for edge in doc.edges:
        if edge.source not in by_id or edge.target not in by_id:
            errors.append(_err("graph.edge.invalid"))

    chats = [n for n in doc.nodes if n.type == "chat_input"]
    if len(chats) > 1:
        errors.append(_err("graph.chatInput.duplicate", chats[1].id))
    orchestrators = [n for n in doc.nodes if n.type == "orchestrator"]
    if len(orchestrators) > 1:
        errors.append(_err("graph.orchestrator.duplicate", orchestrators[1].id))
    if orchestrators:
        orch = orchestrators[0]
        chat_edges = [e for e in doc.edges if chats and e.source == chats[0].id]
        if not chats or not any(
            e.target == orch.id and e.target_handle == "message" for e in chat_edges
        ):
            errors.append(_err("graph.orchestrator.noChat", orch.id))
        if any(e.target != orch.id for e in chat_edges):
            errors.append(_err("graph.orchestrator.fanout", chats[0].id if chats else orch.id))
        if not any(
            e.source == orch.id
            and e.source_handle == "message"
            and by_id.get(e.target) is not None
            and by_id[e.target].type == "end"
            for e in doc.edges
        ):
            errors.append(_err("graph.orchestrator.noEnd", orch.id))
        llm_in = [e for e in doc.edges if e.target == orch.id and e.target_handle == "llm"]
        if len(llm_in) != 1:
            errors.append(_err("graph.orchestrator.noLlm", orch.id))
    if not any(n.type == "end" for n in doc.nodes):
        errors.append(_err("graph.end.missing"))
    if _has_cycle(doc):
        errors.append(_err("graph.cycle"))

    for edge in doc.edges:
        src = by_id.get(edge.source)
        dst = by_id.get(edge.target)
        if not src or not dst:
            continue
        if src.type == "router":
            pass
        elif src.type == "orchestrator":
            if not _orchestrator_edge_ok(edge, dst):
                errors.append(_err("graph.edge.invalid", src.id))
        elif src.type in _OUT_HANDLES and edge.source_handle not in _OUT_HANDLES[src.type]:
            errors.append(_err("graph.edge.invalid", src.id))
        if dst.type in _IN_HANDLES and edge.target_handle not in _IN_HANDLES[dst.type]:
            errors.append(_err("graph.edge.invalid", dst.id))
        if src.type == "knowledge" and not (dst.type == "agent" and edge.target_handle == "knowledge"):
            errors.append(_err("graph.edge.invalid", src.id))
        if src.type == "tool" and not (dst.type == "agent" and edge.target_handle == "tool"):
            errors.append(_err("graph.edge.invalid", src.id))
        if src.type == "llm" and not (
            dst.type in {"agent", "orchestrator"} and edge.target_handle == "llm"
        ):
            errors.append(_err("graph.edge.invalid", src.id))

    has_chat = bool(chats)
    for node in doc.nodes:
        if node.type == "agent":
            llm_in = [
                e
                for e in doc.edges
                if e.target == node.id and e.target_handle == "llm"
            ]
            if len(llm_in) != 1:
                errors.append(_err("graph.agent.noLlm", node.id))
            channel_in = [
                e
                for e in doc.edges
                if e.target == node.id and e.target_handle == "channel"
            ]
            msg_in = [
                e
                for e in doc.edges
                if e.target == node.id and e.target_handle == "message"
            ]
            pipeline_out = [
                e
                for e in doc.edges
                if e.source == node.id and e.source_handle in {"message", "handoff"}
            ]
            if len(channel_in) > 1:
                errors.append(_err("graph.agent.channel", node.id))
            if channel_in and (msg_in or pipeline_out):
                errors.append(_err("graph.agent.mode", node.id))
            if orchestrators and not channel_in:
                errors.append(_err("graph.orchestrator.looseAgent", node.id))
            elif has_chat and not channel_in and not msg_in:
                errors.append(_err("graph.agent.noLlm", node.id))
        if node.type == "llm":
            provider = str(node.data.get("provider") or "ollama")
            model = str(node.data.get("model") or "").strip()
            if provider not in PROVIDERS:
                errors.append(_err("graph.llm.credential", node.id))
            if not model:
                errors.append(_err("graph.llm.credential", node.id))
            if provider in NEEDS_CREDENTIAL and not str(node.data.get("credentialId") or "").strip():
                errors.append(_err("graph.llm.credential", node.id))
        if node.type == "tool":
            kind = str(node.data.get("kind") or "")
            if kind == "mcp":
                if not mcp_available:
                    errors.append(_err("graph.mcp.unavailable", node.id))
                server_id = str(node.data.get("mcpServerId") or "")
                if not server_id:
                    errors.append(_err("graph.mcp.server", node.id))
                elif mcp_enabled is not None and not mcp_enabled(server_id):
                    errors.append(_err("graph.mcp.disabled", node.id))
                elif mcp_root is not None and mcp_root(server_id) is None:
                    # only if recipe needs root — unknown without recipe; skip unless None always errors
                    pass
            elif kind and kind not in FIRST_PARTY_KINDS:
                errors.append(_err("graph.mcp.server", node.id))
            if kind == "file_access":
                root = str(node.data.get("rootPath") or "").strip()
                if not root:
                    errors.append(_err("graph.fileAccess.root", node.id))
                else:
                    try:
                        root_path = Path(root).expanduser()
                        if not root_path.is_absolute() or is_forbidden_root(root_path):
                            errors.append(_err("graph.fileAccess.root", node.id))
                    except (ValueError, OSError):
                        errors.append(_err("graph.fileAccess.root", node.id))
        if node.type == "knowledge":
            path = str(node.data.get("sourcePath") or "")
            if not _path_ok(path, data_dir):
                errors.append(_err("graph.knowledge.path", node.id))
    return errors


def validate_stored(network_id: str, *, data_dir: str, **kwargs: Any) -> list[ValidationError]:
    from app.db.networks import get_network

    row = get_network(network_id)
    if row is None:
        return [_err("networks.notFound")]
    doc = AgentNetworkDocument.model_validate(row.document)
    return validate_document(doc, data_dir=data_dir, **kwargs)
