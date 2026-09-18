from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from app.common.types import PROVIDERS
from app.db.paths import RAG_DIR_NAME
from app.run.graph_models import AgentNetworkDocument, GraphEdge, GraphNode
from app.run.models import ValidationError
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
    "agent": {"message", "llm", "tool", "knowledge"},
    "router": {"message"},
    "end": {"message"},
}


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
    if not source_path.strip():
        return False
    try:
        real = os.path.realpath(os.path.normpath(source_path))
        root = os.path.realpath(data_dir)
        if os.path.commonpath([real, root]) != root:
            return False
    except (ValueError, OSError):
        return False
    if real in {"/", "\\"} or len(os.path.splitdrive(real)[1].strip("\\/")) == 0:
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
        elif src.type in _OUT_HANDLES and edge.source_handle not in _OUT_HANDLES[src.type]:
            errors.append(_err("graph.edge.invalid", src.id))
        if dst.type in _IN_HANDLES and edge.target_handle not in _IN_HANDLES[dst.type]:
            errors.append(_err("graph.edge.invalid", dst.id))
        if src.type == "knowledge" and not (dst.type == "agent" and edge.target_handle == "knowledge"):
            errors.append(_err("graph.edge.invalid", src.id))
        if src.type == "tool" and not (dst.type == "agent" and edge.target_handle == "tool"):
            errors.append(_err("graph.edge.invalid", src.id))
        if src.type == "llm" and not (dst.type == "agent" and edge.target_handle == "llm"):
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
            msg_in = [
                e
                for e in doc.edges
                if e.target == node.id and e.target_handle == "message"
            ]
            if has_chat and not msg_in:
                errors.append(_err("graph.agent.noLlm", node.id))
        if node.type == "llm":
            provider = str(node.data.get("provider") or "ollama")
            model = str(node.data.get("model") or "").strip()
            if provider not in PROVIDERS:
                errors.append(_err("graph.llm.credential", node.id))
            if not model:
                errors.append(_err("graph.llm.credential", node.id))
            if provider in {"xai", "openai_compat"} and not str(node.data.get("credentialId") or "").strip():
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
