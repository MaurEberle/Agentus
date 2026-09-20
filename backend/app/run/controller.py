from __future__ import annotations

import json
import queue
import threading
import uuid
from typing import Any

from app.common.secrets import mask_obj, mask_text
from app.common.types import ServiceStatus
from app.db.engine import utc_now
from app.db.networks import get_network, touch_network
from app.db.runs import insert_log, insert_run, update_run, upsert_step
from app.http.errors import AppError
from app.run.compile import CompiledGraph, compile_document
from app.run.graph_models import AgentNetworkDocument
from app.run.help_bridge import set_help_degraded
from app.run.knowledge import index_node
from app.run.limits import LOG_PAYLOAD_MAX
from app.run.mcp_bridge import get_mcp
from app.run.models import (
    Activity,
    ActivityDag,
    ActivityTokens,
    ChatMessage,
    LogEvent,
    NodeRuntime,
    RunGraph,
    RunGraphEdge,
    RunGraphNode,
    RunSnapshot,
)
from app.run.resources import start_resources, stop_resources
from app.run.sse import publish
from app.run.validate import validate_document
from app.settings.service import RunSlice, load_settings, set_run_slice_provider

_controller: RunController | None = None


def get_controller() -> RunController:
    global _controller
    if _controller is None:
        _controller = RunController()
    return _controller


class RunController:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.service_status: ServiceStatus = "stopped"
        self.run_id: str | None = None
        self.started_at: str | None = None
        self.network_id: str | None = None
        self.snapshot: RunSnapshot | None = None
        self.stop_event = threading.Event()
        self.abort_generation = threading.Event()
        self.chat_input_queue: queue.Queue[str] = queue.Queue()
        self.thread: threading.Thread | None = None
        self.compiled: CompiledGraph | None = None
        self.conversation: list[ChatMessage] = []
        self._unloads: list[str] = []
        self._help_model: str | None = None
        self.last_error_node_id: str | None = None
        self.tokens_in = 0
        self.tokens_out = 0
        set_run_slice_provider(self.slice)

    def reset(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.service_status = "stopped"
        self.run_id = None
        self.started_at = None
        self.network_id = None
        self.snapshot = None
        self.compiled = None
        self.thread = None
        self.conversation = []
        self._unloads = []
        self._help_model = None
        self.last_error_node_id = None
        self.tokens_in = 0
        self.tokens_out = 0
        self.stop_event = threading.Event()
        self.abort_generation = threading.Event()
        set_run_slice_provider(self.slice)

    def slice(self) -> RunSlice:
        return RunSlice(
            service_status=self.service_status,
            run_id=self.run_id,
            started_at=self.started_at,
        )

    def is_busy(self) -> bool:
        return self.service_status in {"starting", "running", "stopping"}

    def start(self) -> dict[str, str]:
        with self.lock:
            if self.is_busy():
                raise AppError("run.busy", status_code=409)
            self.service_status = "starting"
            self.stop_event.clear()
            self.abort_generation.clear()
            self.chat_input_queue = queue.Queue()
            self.conversation = []
            self.last_error_node_id = None
            self.tokens_in = 0
            self.tokens_out = 0
        publish("service", {"serviceStatus": "starting"})
        try:
            settings = load_settings()
            network_id = settings.active_network_id
            if not network_id:
                raise AppError("run.noActiveNetwork", status_code=409)
            row = get_network(network_id)
            if row is None:
                raise AppError("networks.notFound", status_code=409)
            from app.db.engine import get_bootstrap

            data_dir = str(get_bootstrap().data_dir)
            mcp = get_mcp()
            doc = AgentNetworkDocument.model_validate(row.document)
            has_mcp = any(
                n.type == "tool" and str(n.data.get("kind")) == "mcp" for n in doc.nodes
            )
            if has_mcp and mcp is None:
                raise AppError("graph.mcp.unavailable", status_code=409)
            errors = validate_document(
                doc,
                data_dir=data_dir,
                mcp_enabled=(mcp.is_enabled if mcp else None),
                mcp_root=(mcp.root_path if mcp else None),
                mcp_available=mcp is not None,
            )
            if errors:
                keys = ",".join(e.message_key for e in errors[:8])
                raise AppError("run.invalidNetwork", status_code=409, message=keys)
            compiled = compile_document(doc, network_id=row.id, network_name=row.name)
            for kid in {kid for ag in compiled.agents.values() for kid in ag.knowledge_node_ids}:
                node = compiled.by_id.get(kid)
                if node and index_node(row.id, node, data_dir=data_dir) == "error":
                    raise AppError("run.knowledge.failed", status_code=409)
            fallback_missing = self._vram_start(compiled, settings)
            server_ids = [sid for ag in compiled.agents.values() for sid, _ in ag.mcp if sid]
            if server_ids and mcp is not None:
                mcp.open_for(list(dict.fromkeys(server_ids)))
            run_id = str(uuid.uuid4())
            started = utc_now()
            models: list[dict[str, str]] = []
            seen_models: set[str] = set()
            for agent in compiled.agents.values():
                if not agent.llm.model or agent.llm.model in seen_models:
                    continue
                seen_models.add(agent.llm.model)
                models.append({"provider": agent.llm.provider, "model": agent.llm.model})
            insert_run(
                id=run_id,
                network_id=row.id,
                network_name=row.name,
                started_at=started,
                outcome="running",
                graph_snapshot=doc.model_dump(by_alias=True),
                models=models,
            )
            touch_network(row.id, last_used_at=started, last_run_id=run_id)
            snapshot = _build_snapshot(compiled, run_id, started, "running")
            with self.lock:
                self.run_id = run_id
                self.started_at = started
                self.network_id = row.id
                self.compiled = compiled
                self.snapshot = snapshot
                self.service_status = "running"
            _seed_steps(compiled, run_id)
            publish("service", {"serviceStatus": "running"})
            publish("run", snapshot.model_dump(by_alias=True))
            if fallback_missing:
                emit_log("warn", "run.help.fallbackMissing")
            emit_log(
                "info",
                "run.start",
                payload={"networkId": row.id, "networkName": row.name},
            )
            start_resources()
            from app.run.harness import run_harness

            self.thread = threading.Thread(
                target=run_harness, args=(self, compiled), name="run-harness", daemon=True
            )
            self.thread.start()
            return {"serviceStatus": "running", "runId": run_id}
        except AppError as exc:
            self._fail_start()
            raise exc
        except Exception:
            self._fail_start()
            raise AppError("run.invalidNetwork", status_code=409)

    def _fail_start(self) -> None:
        self.teardown(outcome=None)
        with self.lock:
            self.service_status = "stopped"
            self.run_id = None
        publish("service", {"serviceStatus": "stopped"})

    def stop(self) -> dict[str, str]:
        with self.lock:
            if self.service_status in {"stopped", "disconnected"}:
                return {"serviceStatus": "stopped"}
            self.service_status = "stopping"
        publish("service", {"serviceStatus": "stopping"})
        self.stop_event.set()
        thread = self.thread
        if thread and thread.is_alive():
            thread.join(timeout=10)
        with self.lock:
            already = self.service_status == "stopped"
        if not already:
            self.teardown(outcome="cancelled")
            with self.lock:
                self.service_status = "stopped"
            publish("service", {"serviceStatus": "stopped"})
        return {"serviceStatus": "stopped"}

    def finish(
        self,
        outcome: str,
        *,
        error_message: str | None = None,
        error_class: str | None = None,
        error_node_id: str | None = None,
        error_node_name: str | None = None,
    ) -> None:
        run_id = self.run_id
        if run_id:
            chat = [item.model_dump(by_alias=True) for item in self.conversation] or None
            fields: dict[str, Any] = {
                "outcome": outcome,
                "ended_at": utc_now(),
                "chat": chat,
            }
            if error_message:
                fields["error_message"] = error_message
            if error_class:
                fields["error_class"] = error_class
            if error_node_id:
                fields["error_node_id"] = error_node_id
            if error_node_name:
                fields["error_node_name"] = error_node_name
            update_run(run_id, **fields)
        self.teardown(outcome=outcome)
        with self.lock:
            self.service_status = "stopped"
        publish("service", {"serviceStatus": "stopped"})
        if self.snapshot:
            self.snapshot = self.snapshot.model_copy(update={"service_status": "stopped"})
            publish("run", self.snapshot.model_dump(by_alias=True))

    def teardown(self, outcome: str | None) -> None:
        self.stop_event.set()
        mcp = get_mcp()
        if mcp is not None:
            try:
                mcp.close_all()
            except Exception:
                pass
        from app.runtime.ollama import unload

        for tag in list(self._unloads):
            try:
                unload(tag)
            except Exception:
                pass
        self._unloads.clear()
        if self._help_model:
            try:
                from app.runtime.ollama import ensure_loaded

                ensure_loaded(self._help_model)
            except Exception:
                pass
            self._help_model = None
        set_help_degraded(False)
        stop_resources()

    def _vram_start(self, compiled: CompiledGraph, settings: Any) -> bool:
        from app.runtime.errors import RuntimeApiError
        from app.runtime.ollama import ensure_loaded, list_ollama_models

        fallback_missing = False
        help_chat = settings.help_chat
        if help_chat.provider == "ollama" and help_chat.model.strip():
            set_help_degraded(True)
            fallback = (help_chat.fallback_model or "llama3.2:1b").strip()
            self._help_model = help_chat.model.strip()
            try:
                ensure_loaded(fallback)
                self._unloads.append(fallback)
            except Exception:
                fallback_missing = True
        try:
            installed = {item.name for item in list_ollama_models()}
        except RuntimeApiError as exc:
            raise AppError(exc.error_key, status_code=409) from exc
        seen: set[str] = set()
        for agent in compiled.agents.values():
            if agent.llm.provider != "ollama" or not agent.llm.model:
                continue
            tag = agent.llm.model
            if tag in seen:
                continue
            seen.add(tag)
            if tag not in installed and f"{tag}:latest" not in installed:
                raise AppError("runtime.modelNotFound", status_code=409, message=tag)
        return fallback_missing

    def send_chat(self, text: str) -> None:
        with self.lock:
            if self.service_status != "running" or not self.compiled or not self.compiled.chat_input:
                raise AppError("run.busy", status_code=409)
            run_id = self.run_id or ""
        self.chat_input_queue.put(text)
        msg = ChatMessage(
            id=str(uuid.uuid4()),
            run_id=run_id,
            role="user",
            content=mask_text(text),
            created_at=utc_now(),
        )
        self.conversation.append(msg)
        publish("chat", {"runId": run_id, "message": msg.model_dump(by_alias=True)})

    def abort_chat(self) -> None:
        self.abort_generation.set()


def node_label(compiled: CompiledGraph | None, node_id: str | None) -> str | None:
    if compiled is None or not node_id:
        return None
    node = compiled.by_id.get(node_id)
    if node is None:
        return None
    name = str(node.data.get("displayName") or "").strip()
    return name or node.type


def _seed_steps(compiled: CompiledGraph, run_id: str) -> None:
    for node in compiled.doc.nodes:
        role = str(node.data.get("role") or "").strip() or None
        upsert_step(
            run_id=run_id,
            node_id=node.id,
            node_name=node_label(compiled, node.id),
            role=role,
            type=node.type,
            status="idle",
        )


def emit_log(
    level: str,
    message: str,
    *,
    node_id: str | None = None,
    node_name: str | None = None,
    payload: object | None = None,
    stack: str | None = None,
) -> None:
    ctrl = get_controller()
    run_id = ctrl.run_id or ""
    if node_name is None:
        node_name = node_label(ctrl.compiled, node_id)
    if payload is not None:
        dumped = json.dumps(mask_obj(payload), ensure_ascii=False, default=str)
        if len(dumped) > LOG_PAYLOAD_MAX:
            dumped = dumped[:LOG_PAYLOAD_MAX]
            try:
                payload = json.loads(dumped)
            except json.JSONDecodeError:
                payload = {"truncated": True}
        else:
            payload = json.loads(dumped)
    event = LogEvent(
        id=str(uuid.uuid4()),
        ts=utc_now(),
        level=level,  # type: ignore[arg-type]
        run_id=run_id,
        node_id=node_id,
        node_name=node_name,
        message=mask_text(message),
        payload=payload,
        stack=mask_text(stack) if stack else None,
    )
    if run_id:
        insert_log(
            run_id=run_id,
            message=event.message,
            id=event.id,
            ts=event.ts,
            level=level,
            node_id=node_id,
            node_name=node_name,
            payload=payload,
            stack=event.stack,
        )
    publish("log", event.model_dump(by_alias=True))


def _build_snapshot(
    compiled: CompiledGraph, run_id: str, started: str, status: ServiceStatus
) -> RunSnapshot:
    nodes = []
    for node in compiled.doc.nodes:
        data = {k: v for k, v in node.data.items() if k.lower() not in {"secret", "password", "token", "apikey"}}
        nodes.append(
            RunGraphNode(id=node.id, type=node.type, position=node.position, data=data)
        )
    edges = [
        RunGraphEdge(
            id=e.id,
            source=e.source,
            source_handle=e.source_handle,
            target=e.target,
            target_handle=e.target_handle,
        )
        for e in compiled.doc.edges
    ]
    runtime = {n.id: NodeRuntime(status="idle") for n in compiled.doc.nodes}
    chat = None
    if compiled.chat_input:
        chat = {"messages": [], "generating": False}
    total = len(compiled.agents) + len(compiled.end_ids) + len(compiled.routers)
    return RunSnapshot(
        run_id=run_id,
        network_id=compiled.network_id,
        network_name=compiled.network_name,
        started_at=started,
        service_status=status,
        graph=RunGraph(nodes=nodes, edges=edges),
        nodes_runtime=runtime,
        activity=Activity(
            current_node_ids=[],
            dag=ActivityDag(
                completed=0,
                total=total,
                pending_node_ids=list(compiled.agents),
            ),
            tokens=ActivityTokens(out=0),
        ),
        chat=chat,
    )


get_controller()
