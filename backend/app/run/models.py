from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.common.types import ServiceStatus
from app.http.app import ApiModel

NodeRuntimeStatus = Literal["idle", "waiting", "running", "done", "error"]
WaitReason = Literal["none", "llm", "tool", "human", "index", "knowledge"]
LogLevel = Literal["debug", "info", "warn", "error"]


class NodeTokens(ApiModel):
    in_: int | None = Field(default=None, alias="in")
    out: int | None = None
    per_second: float | None = Field(default=None, alias="perSecond")
    context_used: int | None = Field(default=None, alias="contextUsed")
    context_max: int | None = Field(default=None, alias="contextMax")


class NodeLlmInfo(ApiModel):
    model: str = ""
    provider: str = "ollama"
    node_id: str = Field(default="", alias="nodeId")


class NodeRuntime(ApiModel):
    status: NodeRuntimeStatus = "idle"
    role: str | None = None
    wait_reason: WaitReason | None = Field(default=None, alias="waitReason")
    last_message: str | None = Field(default=None, alias="lastMessage")
    error: str | None = None
    llm: NodeLlmInfo | None = None
    tokens: NodeTokens | None = None


class RunGraphNode(ApiModel):
    id: str
    type: str
    position: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


class RunGraphEdge(ApiModel):
    id: str
    source: str
    source_handle: str | None = Field(default=None, alias="sourceHandle")
    target: str
    target_handle: str | None = Field(default=None, alias="targetHandle")


class RunGraph(ApiModel):
    nodes: list[RunGraphNode]
    edges: list[RunGraphEdge]


class ChatMessage(ApiModel):
    id: str
    run_id: str = Field(alias="runId")
    role: Literal["user", "assistant"]
    content: str
    created_at: str = Field(alias="createdAt")
    message_key: str | None = Field(default=None, alias="messageKey")
    message_params: dict[str, Any] | None = Field(default=None, alias="messageParams")


class ActivityDag(ApiModel):
    completed: int
    total: int
    pending_node_ids: list[str] = Field(alias="pendingNodeIds")


class ActivityTokens(ApiModel):
    in_: int | None = Field(default=None, alias="in")
    out: int | None = None
    per_second: float | None = Field(default=None, alias="perSecond")


class Activity(ApiModel):
    current_node_ids: list[str] = Field(default_factory=list, alias="currentNodeIds")
    dag: ActivityDag | None = None
    tokens: ActivityTokens | None = None


class RunSnapshot(ApiModel):
    run_id: str = Field(alias="runId")
    network_id: str = Field(alias="networkId")
    network_name: str = Field(alias="networkName")
    started_at: str = Field(alias="startedAt")
    service_status: ServiceStatus = Field(alias="serviceStatus")
    error_message: str | None = Field(default=None, alias="errorMessage")
    graph: RunGraph
    nodes_runtime: dict[str, NodeRuntime] = Field(default_factory=dict, alias="nodesRuntime")
    activity: Activity = Field(default_factory=Activity)
    chat: dict[str, Any] | None = None


class LogEvent(ApiModel):
    id: str
    ts: str
    level: LogLevel
    run_id: str = Field(alias="runId")
    node_id: str | None = Field(default=None, alias="nodeId")
    node_name: str | None = Field(default=None, alias="nodeName")
    message: str
    payload: Any = None
    stack: str | None = None


class ResourceGpu(ApiModel):
    index: int
    name: str | None = None
    util_percent: float = Field(alias="utilPercent")
    vram_used_bytes: int = Field(alias="vramUsedBytes")
    vram_total_bytes: int = Field(alias="vramTotalBytes")


class ResourceSnapshot(ApiModel):
    ts: str
    cpu_percent: float = Field(alias="cpuPercent")
    ram_used_bytes: int = Field(alias="ramUsedBytes")
    ram_total_bytes: int = Field(alias="ramTotalBytes")
    gpus: list[ResourceGpu] | None = None
    scope: Literal["host"] = "host"


class ValidationError(ApiModel):
    node_id: str | None = Field(default=None, alias="nodeId")
    message_key: str = Field(alias="messageKey")
