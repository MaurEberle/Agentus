"""Outer run loop for a linear chain and for the orchestrator round."""

from __future__ import annotations

import logging
import traceback
import uuid
from collections import deque

from app.db.engine import utc_now
from app.run import agent_turn, dispatch, orchestrator_decide, turn_runtime
from app.run.compile import CompiledGraph
from app.run.controller import RunController, emit_log, node_label
from app.run.limits import (
    MAX_AGENT_INVOCATIONS,
    MAX_ORCHESTRATOR_STEPS,
    MAX_ORCHESTRATOR_THINKS,
    MAX_SHORT_THINKS,
    MAX_TAKEOVER_THINKS,
)
from app.run.memory import RunMemory
from app.run.models import ChatMessage
from app.run.orchestrate import orchestrator_instructions
from app.run.router_rules import resolve_route
from app.run.turn_runtime import _FILE_MUTATIONS
from app.run.wait_ask import excerpt as ask_excerpt
from app.runtime.errors import RuntimeApiError
from app.runtime.models import ChatMessage as LlmMessage

log = logging.getLogger("agentus.run")

_FINISH_FILES_NOTE = (
    "A coding agent made no successful write or delete and returned no text. "
    "Check with a tool or call that agent again. Finish only when the files exist."
)


def _run_error_class(exc: BaseException) -> str:
    if isinstance(exc, RuntimeApiError) and exc.error_key == "runtime.timeout":
        return "timeout"
    if isinstance(exc, RuntimeApiError) and str(exc.error_key).startswith("runtime."):
        return "llm_error"
    return "unknown"

def run_harness(ctrl: RunController, compiled: CompiledGraph) -> None:
    outcome = "failed"
    fail_exc: BaseException | None = None
    try:
        user_text = _wait_user(ctrl, compiled)
        if ctrl.stop_event.is_set():
            outcome = "cancelled"
            return
        if compiled.chat_input is None:
            emit_log("info", "run.batch.start")
            user_text = user_text or ""
        elif user_text:
            emit_log(
                "info",
                "run.chat.user",
                node_id=compiled.chat_input.id,
                payload={"chars": len(user_text)},
            )
            _clear_human_wait(ctrl, compiled)
        if compiled.orchestrator is not None:
            outcome = _run_orchestrator(ctrl, compiled, user_text or "")
        else:
            outcome = _run_linear(ctrl, compiled, user_text or "")
    except Exception as exc:
        fail_exc = exc
        log_message = str(exc)
        payload = turn_runtime._runtime_error_payload(exc)
        if isinstance(exc, RuntimeApiError) and exc.error_key == "runtime.modelInfoFailed":
            log_message = "run.llm.modelInfo"
            detail = {"model": exc.detail or ""}
            payload = {**(payload or {}), **detail}
            log.error("ollama model info failed model=%s", exc.detail or "")
        emit_log(
            "error",
            log_message,
            payload=payload,
            stack=traceback.format_exc(),
        )
        outcome = "failed"
    finally:
        if outcome == "succeeded":
            emit_log("info", "run.succeeded")
        elif outcome == "cancelled":
            emit_log("warn", "run.cancelled")
        else:
            emit_log("error", "run.failed")
        extra: dict[str, str] = {}
        if outcome == "failed" and fail_exc is not None:
            extra["error_message"] = str(fail_exc)[:500]
            extra["error_class"] = _run_error_class(fail_exc)
        elif outcome == "failed" and ctrl.fail_message:
            extra["error_message"] = ctrl.fail_message
            extra["error_class"] = ctrl.fail_class or "orchestrator"
        if outcome == "failed":
            node_id = getattr(ctrl, "last_error_node_id", None)
            if node_id:
                extra["error_node_id"] = node_id
                name = node_label(compiled, node_id)
                if name:
                    extra["error_node_name"] = name
        ctrl.finish(outcome, **extra)

def _wait_user(ctrl: RunController, compiled: CompiledGraph) -> str | None:
    chat = compiled.chat_input
    if chat is None:
        return ""
    data = chat.data
    require_input = bool(data.get("requireInput"))
    start = str(data.get("startMessage") or "").strip()
    if require_input:
        turn_runtime._set_node(ctrl, chat.id, "waiting", wait="human")
        emit_log("info", "run.wait.human", node_id=chat.id)
        return _queue_get(ctrl)
    if start:
        if compiled.chat_input:
            _publish_user(ctrl, start)
        return start
    turn_runtime._set_node(ctrl, chat.id, "waiting", wait="human")
    emit_log("info", "run.wait.human", node_id=chat.id)
    return _queue_get(ctrl)

def _queue_get(ctrl: RunController) -> str | None:
    while not ctrl.stop_event.is_set():
        try:
            return ctrl.chat_input_queue.get(timeout=0.2)
        except Exception:
            continue
    return None

def _route(compiled: CompiledGraph, router_id: str, text: str) -> tuple[str | None, str]:
    router = compiled.routers.get(router_id)
    if router is None:
        return None, "default"
    return resolve_route(router, text)

def _fail_step_limit(ctrl: RunController, node_id: str) -> str:
    emit_log("error", "run.stepLimit", node_id=node_id)
    ctrl.fail_message = "run.stepLimit"
    ctrl.fail_class = "orchestrator"
    ctrl.last_error_node_id = node_id
    turn_runtime._set_node(ctrl, node_id, "error", error="run.stepLimit")
    return "failed"

def _fail_think_limit(ctrl: RunController, node_id: str) -> str:
    emit_log("error", "run.orchestrator.thinkLimit", node_id=node_id)
    ctrl.fail_message = "run.orchestrator.thinkLimit"
    ctrl.fail_class = "orchestrator"
    ctrl.last_error_node_id = node_id
    turn_runtime._set_node(ctrl, node_id, "error", error="run.orchestrator.thinkLimit")
    return "failed"

def _fail_takeover(ctrl: RunController, node_id: str, memory: RunMemory, *, no_tool: bool = False) -> str:
    item = memory.takeover
    name = item.name if item else ""
    task = item.task if item else ""
    misses = memory.misses.get(item.agent_id, 0) if item else 0
    key = "run.orchestrator.takeoverNoTool" if no_tool else "run.orchestrator.takeover"
    emit_log(
        "error",
        key,
        node_id=node_id,
        payload={"agent": name, "misses": misses, "task": task[:300]},
    )
    ctrl.fail_message = key
    ctrl.fail_class = "orchestrator"
    ctrl.last_error_node_id = node_id
    turn_runtime._set_node(ctrl, node_id, "error", error=key)
    return "failed"

def _fail_think_loop(ctrl: RunController, node_id: str, thinks: int) -> str:
    emit_log("error", "run.orchestrator.thinkLoop", node_id=node_id, payload={"thinks": thinks})
    ctrl.fail_message = "run.orchestrator.thinkLoop"
    ctrl.fail_class = "orchestrator"
    ctrl.last_error_node_id = node_id
    turn_runtime._set_node(ctrl, node_id, "error", error="run.orchestrator.thinkLoop")
    return "failed"

def _run_linear(ctrl: RunController, compiled: CompiledGraph, user_text: str) -> str:
    conversation: list[LlmMessage] = []
    if user_text:
        conversation.append(LlmMessage(role="user", content=user_text))
    pending: deque[tuple[str, str]] = deque()
    if compiled.chat_input:
        for edge in compiled.doc.edges:
            if edge.source == compiled.chat_input.id:
                pending.append((edge.target, user_text or ""))
    else:
        for agent_id in compiled.topo_agents:
            pending.append((agent_id, user_text or ""))
    end_hit: set[str] = set()
    invocations = 0
    while pending and not ctrl.stop_event.is_set():
        node_id, payload = pending.popleft()
        node = compiled.by_id.get(node_id)
        if node is None:
            continue
        if node.type == "end":
            end_hit.add(node_id)
            turn_runtime._set_node(ctrl, node_id, "done")
            emit_log("debug", "run.end", node_id=node_id)
            continue
        if node.type == "router":
            target, branch = _route(compiled, node_id, payload)
            if target is None:
                emit_log("error", "graph.router.noEdge", node_id=node_id, payload={"branch": branch})
                ctrl.fail_message = "graph.router.noEdge"
                ctrl.last_error_node_id = node_id
                turn_runtime._set_node(ctrl, node_id, "error", error="graph.router.noEdge")
                return "failed"
            emit_log(
                "info",
                "run.router",
                node_id=node_id,
                payload={"target": target, "branch": branch},
            )
            turn_runtime._set_node(ctrl, node_id, "done")
            pending.append((target, payload))
            continue
        if node.type != "agent":
            continue
        invocations += 1
        if invocations > MAX_AGENT_INVOCATIONS:
            return _fail_step_limit(ctrl, node_id)
        text = agent_turn._agent_turn(ctrl, compiled, node_id, payload, conversation)
        if text is None:
            if ctrl.stop_event.is_set():
                break
            return "failed" if ctrl.fail_message else "cancelled"
        for target in compiled.agents[node_id].outbound_message:
            pending.append((target, text))
    if ctrl.stop_event.is_set():
        return "cancelled"
    if end_hit:
        return "succeeded"
    return "failed"

def _run_orchestrator(ctrl: RunController, compiled: CompiledGraph, user_text: str) -> str:
    orch = compiled.orchestrator
    if orch is None:
        return "failed"
    memory = RunMemory()
    memory.miss_limit = orch.agent_miss_limit
    if user_text:
        memory.add_user(user_text)
    roster: list[tuple[str, str, str]] = []
    for agent_id in orch.agents:
        node = compiled.by_id.get(agent_id)
        name = agent_id
        instructions = ""
        if node is not None:
            name = str(node.data.get("displayName") or node.data.get("role") or agent_id).strip() or agent_id
            instructions = str(node.data.get("systemPrompt") or "")
        roster.append((agent_id, name, instructions))
    tool_schemas = turn_runtime._tool_schemas(
        orch.tool_kinds,
        orch.mcp,
        orch.file_actions,
        terminal_programs=orch.terminal_programs,
        terminal_unrestricted=orch.terminal_unrestricted,
    )
    names = [(agent_id, name) for agent_id, name, _ in roster]
    steps = 0
    thinks = 0
    short_thinks = 0
    spoke = False
    while not ctrl.stop_event.is_set():
        offered = tool_schemas if memory.allow_own_tools or memory.takeover is not None else []
        system = orchestrator_instructions(
            orch.system_prompt,
            roster,
            turn_runtime._function_names(offered),
            takeover=memory.takeover is not None,
        )
        action = orchestrator_decide._orchestrator_action(ctrl, compiled, system, memory, offered, names, block_reply=spoke)
        tokens = orchestrator_decide._pop_tokens(action)
        memory.clear_anomaly()
        _store_memory(ctrl, memory)
        if action is None:
            return "cancelled" if ctrl.stop_event.is_set() else "failed"
        if action.get("action") == "failed-window":
            turn_runtime._set_node(ctrl, orch.node_id, "error", error="run.orchestrator.window")
            return "failed"
        if action.get("action") == "failed-tools":
            return "failed"
        if action.get("action") == "unreadable":
            ctrl.fail_message = "run.orchestrator.unreadable"
            ctrl.fail_class = "orchestrator"
            ctrl.last_error_node_id = orch.node_id
            emit_log("error", "run.orchestrator.unreadable", node_id=orch.node_id)
            turn_runtime._set_node(ctrl, orch.node_id, "error", error="run.orchestrator.unreadable")
            return "failed"
        if action.get("action") in {"think", "defer"}:
            body = (action.get("text") or "").strip()
            emit_log(
                "info",
                "run.orchestrator.think",
                node_id=orch.node_id,
                payload={"text": body},
            )
            turn_runtime._set_node(ctrl, orch.node_id, "running", wait="thinking")
            thinks += 1
            if tokens is not None and tokens <= 1:
                short_thinks += 1
            else:
                short_thinks = 0
            if short_thinks >= MAX_SHORT_THINKS:
                _store_memory(ctrl, memory)
                turn_runtime._set_llm(ctrl, compiled, orch.llm.node_id or orch.node_id, busy=False)
                return _fail_think_loop(ctrl, orch.node_id, short_thinks)
            if memory.takeover and thinks > MAX_TAKEOVER_THINKS:
                _store_memory(ctrl, memory)
                turn_runtime._set_llm(ctrl, compiled, orch.llm.node_id or orch.node_id, busy=False)
                return _fail_takeover(ctrl, orch.node_id, memory)
            if thinks >= MAX_ORCHESTRATOR_THINKS:
                _store_memory(ctrl, memory)
                turn_runtime._set_llm(ctrl, compiled, orch.llm.node_id or orch.node_id, busy=False)
                return _fail_think_limit(ctrl, orch.node_id)
            continue
        kind = action.get("action") or "reply"
        text = action.get("text") or ""
        emit_log(
            "info",
            "run.orchestrator.action",
            node_id=orch.node_id,
            payload={"action": kind, "agent": action.get("agent") or ""},
        )
        if kind == "ask":
            spoke = False
            thinks = 0
            short_thinks = 0
            _speak(ctrl, compiled, memory, "ask", text or "…", wait=True)
            reply = _queue_get(ctrl)
            if not reply or ctrl.stop_event.is_set():
                return "cancelled"
            memory.add_user(reply)
            _clear_human_wait(ctrl, compiled)
            continue
        if kind == "call":
            spoke = False
            thinks = 0
            short_thinks = 0
            if memory.refuses_agent(action.get("agent") or "", names):
                memory.takeover_rejects += 1
                closed = memory.takeover
                emit_log(
                    "warn",
                    "run.orchestrator.takeoverBlocked",
                    node_id=orch.node_id,
                    payload={"agent": closed.name if closed else ""},
                )
                if memory.takeover_rejects >= 2:
                    _store_memory(ctrl, memory)
                    return _fail_takeover(ctrl, orch.node_id, memory)
                memory.add_note("That agent is closed for this task. Use your tools. Do not call it.")
                continue
            if steps >= MAX_ORCHESTRATOR_STEPS:
                _store_memory(ctrl, memory)
                return _fail_step_limit(ctrl, orch.node_id)
            outcome = dispatch._orchestrator_call(ctrl, compiled, memory, names, action, user_text)
            if outcome == "cancelled":
                return "cancelled"
            if memory.takeover_unarmed:
                _store_memory(ctrl, memory)
                return _fail_takeover(ctrl, orch.node_id, memory, no_tool=True)
            if outcome == "ran":
                steps += 1
            continue
        if kind == "finish":
            if memory.takeover:
                _store_memory(ctrl, memory)
                return _fail_takeover(ctrl, orch.node_id, memory)
            if _tool_work_unverified(memory) and not memory.finish_warned:
                memory.finish_warned = True
                memory.add_note(_FINISH_FILES_NOTE)
                continue
            if text.strip():
                _publish_assistant(ctrl, text.strip())
                memory.add_spoken("finish", text.strip())
            _finish_targets(ctrl, compiled, orch, text)
            _store_memory(ctrl, memory)
            return "succeeded"
        if memory.takeover:
            _store_memory(ctrl, memory)
            return _fail_takeover(ctrl, orch.node_id, memory)
        if text.strip():
            _publish_assistant(ctrl, text.strip())
            memory.add_spoken("reply", text.strip())
        spoke = True
        thinks = 0
        short_thinks = 0
        continue
    _store_memory(ctrl, memory)
    turn_runtime._set_llm(ctrl, compiled, orch.llm.node_id or orch.node_id, busy=False)
    return "cancelled"

def _tool_work_unverified(memory: RunMemory) -> bool:
    called = [rec for rec in memory.records if rec.has_tools]
    if not called:
        return False
    if any(
        fact.ok and fact.action in _FILE_MUTATIONS
        for rec in called
        for fact in rec.files
    ):
        return False
    return any(rec.finished and not (rec.text or "").strip() for rec in called)

def _finish_targets(ctrl: RunController, compiled: CompiledGraph, orch, text: str) -> None:
    for target in orch.finals:
        node = compiled.by_id.get(target)
        if node is None:
            continue
        if node.type == "end":
            turn_runtime._set_node(ctrl, target, "done")
            emit_log("debug", "run.end", node_id=target)
        elif node.type == "router":
            nxt, branch = _route(compiled, target, text)
            emit_log(
                "info",
                "run.router",
                node_id=target,
                payload={"target": nxt or "", "branch": branch},
            )
            end = compiled.by_id.get(nxt or "")
            if end is not None and end.type == "end":
                turn_runtime._set_node(ctrl, target, "done")
                turn_runtime._set_node(ctrl, end.id, "done")
                emit_log("debug", "run.end", node_id=end.id)
    turn_runtime._set_node(ctrl, orch.node_id, "done")
    if compiled.chat_input:
        turn_runtime._set_node(ctrl, compiled.chat_input.id, "done")

def _speak(
    ctrl: RunController,
    compiled: CompiledGraph,
    memory: RunMemory,
    kind: str,
    text: str,
    *,
    wait: bool,
) -> None:
    _publish_assistant(ctrl, text)
    memory.add_spoken(kind, text)
    if wait:
        _begin_ask(ctrl, compiled, text)
        _wait_chat(ctrl, compiled)

def _begin_ask(ctrl: RunController, compiled: CompiledGraph, text: str) -> None:
    orch = compiled.orchestrator
    node_id = orch.node_id if orch is not None else (compiled.chat_input.id if compiled.chat_input else None)
    speaker = node_label(compiled, node_id) or "orchestrator"
    clipped = ask_excerpt(text)
    ask = ctrl.set_wait_ask(speaker=speaker, excerpt=clipped, node_id=node_id)
    emit_log(
        "info",
        "run.wait.ask",
        node_id=node_id,
        payload={"id": ask.id, "speaker": speaker, "excerpt": clipped},
    )

def _wait_chat(ctrl: RunController, compiled: CompiledGraph) -> None:
    orch = compiled.orchestrator
    if orch is not None:
        turn_runtime._set_node(ctrl, orch.node_id, "waiting", wait="human")
    if compiled.chat_input:
        turn_runtime._set_node(ctrl, compiled.chat_input.id, "waiting", wait="human")
    emit_log("info", "run.wait.human", node_id=orch.node_id if orch else None)

def _clear_human_wait(ctrl: RunController, compiled: CompiledGraph) -> None:
    ctrl.clear_wait_ask()
    if compiled.chat_input:
        turn_runtime._set_node(ctrl, compiled.chat_input.id, "idle")
    orch = compiled.orchestrator
    if orch is not None:
        turn_runtime._set_node(ctrl, orch.node_id, "idle")

def _store_memory(ctrl: RunController, memory: RunMemory) -> None:
    if not ctrl.run_id:
        return
    try:
        from app.db.runs import update_run

        update_run(ctrl.run_id, memory=memory.to_dict())
    except Exception:
        return

def _publish_assistant(ctrl: RunController, text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        return
    msg = ChatMessage(
        id=str(uuid.uuid4()),
        run_id=ctrl.run_id or "",
        role="assistant",
        content=cleaned,
        created_at=utc_now(),
    )
    ctrl.remember_chat(msg, generating=False)

def _publish_user(ctrl: RunController, text: str) -> None:
    msg = ChatMessage(
        id=str(uuid.uuid4()),
        run_id=ctrl.run_id or "",
        role="user",
        content=text,
        created_at=utc_now(),
    )
    ctrl.remember_chat(msg, generating=True)

