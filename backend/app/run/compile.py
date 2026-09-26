from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from app.run.channels import normalize_channel_edges
from app.run.graph_models import AgentNetworkDocument, GraphNode


@dataclass
class CompiledLlm:
    provider: str
    model: str
    base_url: str | None
    credential_id: str | None
    temperature: float | None
    max_tokens: int | None
    num_ctx: int | None
    node_id: str


@dataclass
class CompiledOrchestrator:
    node_id: str
    system_prompt: str
    llm: CompiledLlm
    agents: list[str]
    finals: list[str]


@dataclass
class CompiledAgent:
    node_id: str
    system_prompt: str
    llm: CompiledLlm
    tool_kinds: list[str]
    mcp: list[tuple[str, list[str] | None]]
    knowledge_node_ids: list[str]
    outbound_message: list[str]


@dataclass
class CompiledGraph:
    network_id: str
    network_name: str
    doc: AgentNetworkDocument
    agents: dict[str, CompiledAgent]
    orchestrator: CompiledOrchestrator | None
    chat_input: GraphNode | None
    end_ids: list[str]
    routers: dict[str, list[tuple[str, str]]]
    topo_agents: list[str]
    by_id: dict[str, GraphNode] = field(default_factory=dict)


def _compile_llm(doc: AgentNetworkDocument, by_id: dict[str, GraphNode], node_id: str) -> CompiledLlm:
    llm_edges = [e for e in doc.edges if e.target == node_id and e.target_handle == "llm"]
    llm_node = by_id[llm_edges[0].source] if llm_edges else None
    data = llm_node.data if llm_node else {}
    return CompiledLlm(
        provider=str(data.get("provider") or "ollama"),
        model=str(data.get("model") or ""),
        base_url=data.get("baseUrl"),
        credential_id=data.get("credentialId"),
        temperature=data.get("temperature"),
        max_tokens=data.get("maxTokens"),
        num_ctx=_num_ctx(data),
        node_id=llm_node.id if llm_node else "",
    )


def _num_ctx(data: dict) -> int | None:
    raw = data.get("numCtx")
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int) and raw > 0:
        return raw
    if isinstance(raw, float) and raw > 0:
        return int(raw)
    return None


def _compile_orchestrator(
    doc: AgentNetworkDocument, by_id: dict[str, GraphNode]
) -> CompiledOrchestrator | None:
    nodes = [node for node in doc.nodes if node.type == "orchestrator"]
    if not nodes:
        return None
    node = nodes[0]
    agents: list[str] = []
    finals: list[str] = []
    for edge in doc.edges:
        if edge.source != node.id:
            continue
        target = by_id.get(edge.target)
        if target is None:
            continue
        if (
            edge.source_handle == f"channel:{target.id}"
            and target.type == "agent"
            and target.id not in agents
        ):
            agents.append(target.id)
        elif edge.source_handle == "message":
            finals.append(target.id)
    return CompiledOrchestrator(
        node_id=node.id,
        system_prompt=str(node.data.get("systemPrompt") or ""),
        llm=_compile_llm(doc, by_id, node.id),
        agents=agents,
        finals=finals,
    )


def compile_document(
    doc: AgentNetworkDocument, *, network_id: str, network_name: str
) -> CompiledGraph:
    doc = normalize_channel_edges(doc)
    by_id = {n.id: n for n in doc.nodes}
    chats = [n for n in doc.nodes if n.type == "chat_input"]
    chat_input = chats[0] if chats else None
    end_ids = [n.id for n in doc.nodes if n.type == "end"]
    routers: dict[str, list[tuple[str, str]]] = {}
    for node in doc.nodes:
        if node.type != "router":
            continue
        routers[node.id] = [
            (e.source_handle, e.target)
            for e in doc.edges
            if e.source == node.id
        ]

    agents: dict[str, CompiledAgent] = {}
    orchestrator = _compile_orchestrator(doc, by_id)
    for node in doc.nodes:
        if node.type != "agent":
            continue
        llm = _compile_llm(doc, by_id, node.id)
        tool_kinds: list[str] = []
        mcp: list[tuple[str, list[str] | None]] = []
        for edge in doc.edges:
            if edge.target != node.id or edge.target_handle != "tool":
                continue
            tool = by_id.get(edge.source)
            if not tool:
                continue
            kind = str(tool.data.get("kind") or "")
            if kind == "mcp":
                names = tool.data.get("mcpToolNames")
                mcp.append(
                    (
                        str(tool.data.get("mcpServerId") or ""),
                        list(names) if isinstance(names, list) else None,
                    )
                )
            elif kind:
                tool_kinds.append(kind)
        knowledge_ids = [
            e.source
            for e in doc.edges
            if e.target == node.id and e.target_handle == "knowledge"
        ]
        outbound = [
            e.target
            for e in doc.edges
            if e.source == node.id and e.source_handle in {"message", "handoff"}
        ]
        agents[node.id] = CompiledAgent(
            node_id=node.id,
            system_prompt=str(node.data.get("systemPrompt") or ""),
            llm=llm,
            tool_kinds=tool_kinds,
            mcp=mcp,
            knowledge_node_ids=knowledge_ids,
            outbound_message=outbound,
        )

    topo = list(agents.keys())
    return CompiledGraph(
        network_id=network_id,
        network_name=network_name,
        doc=AgentNetworkDocument.model_validate(deepcopy(doc.model_dump(by_alias=True))),
        agents=agents,
        orchestrator=orchestrator,
        chat_input=chat_input,
        end_ids=end_ids,
        routers=routers,
        topo_agents=topo,
        by_id=by_id,
    )
