"""Outer run loop for a linear chain and for the orchestrator round."""

from __future__ import annotations

import logging
import queue
import traceback
import uuid
from collections import deque

from app.db.engine import utc_now
from app.run import agent_turn, dispatch, orch_tools, orchestrator_decide, turn_runtime
from app.run.capabilities import orchestrator_capabilities
from app.run.compile import CompiledGraph
from app.run.controller import RunController, emit_log, node_label
from app.run.limits import (
    IDLE_NUDGE_DECISIONS,
    MAX_IDLE_DECISIONS,
    MAX_LLM_PAUSES,
    MAX_TAKEOVER_REJECTS,
    MAX_TAKEOVER_UNAVAILABLE,
    MAX_AGENT_INVOCATIONS,
    MAX_ORCHESTRATOR_STEPS,
    MAX_ORCHESTRATOR_THINKS,
    MAX_ORCHESTRATOR_TOOL_CALLS,
    MAX_ORIENTATION_CALLS,
    MAX_READ_DECISION_CALLS,
    MAX_SHORT_THINKS,
    MAX_TAKEOVER_THINKS,
    MAX_UNREADABLE_STREAK,
)
from app.run.memory import RunMemory
from app.run.models import ChatMessage
from app.run.orchestrate import RUN_VERBS, WRITE_VERBS, orchestrator_instructions
from app.run.router_rules import resolve_route
from app.run.turn_runtime import _FILE_MUTATIONS
from app.run.wait_ask import excerpt as ask_excerpt
from app.runtime.errors import RuntimeApiError
from app.runtime.models import ChatMessage as LlmMessage

log = logging.getLogger("agentus.run")

_BLOCKED_REPLY_NOTE = (
    "Your last text was not shown: you already replied and a second reply is not allowed. "
    "It is kept above as your plan. Next emit call, ask, or finish. "
    "To end the run with that text, use finish."
)

_REPEAT_THINK_NOTE = (
    "You repeated the same plan. Do not think again. Act on it now: emit call, ask, or finish."
)

_ASK_SUPERSEDED_NOTE = (
    "The user wrote a new message while you were deciding, so your question was not shown: {question} "
    "Read the new message first. Ask again only if it is still unclear."
)

_FINISH_LATE_NOTE = (
    "The user wrote a new message before you finished, so the run did not end. "
    "Handle that message first, then finish."
)

_TAKEOVER_UNAVAILABLE_NOTE = (
    "Takeover is not possible: you do not have the tools for this step. "
    "Decide: call another agent with a clear task, ask the user, or finish and say what is missing."
)

_TAKEOVER_FINISH_NOTE = (
    "Takeover is still open: the file task of the closed agent is not done. "
    "Do it with your tools now. Finish again only to end the run without it."
)

# Linear chain: a step always gets one user message. These stand in when its edge
# carries no text (a start node without a chat input, or a step that returned nothing).
_BATCH_START = "Begin."
_EMPTY_HANDOFF = "(The previous step returned no text.)"

_NATIVE_TOOL_NOTE = (
    'There is no JSON action "{verb}". Your tools are open on this turn: call {tool} with a native tool call, '
    "then decide with one JSON object."
)

_SELF_TAKEOVER_NOTE = (
    "An agent call failed earlier, so you may change files yourself now. "
    'There is no JSON action "{verb}": call file_access with a native tool call '
    "(for example action write with path and content). Write access ends with your next agent call."
)

_WRITE_LOCKED_NOTE = (
    'There is no JSON action "{verb}". Changing files, setup, builds and tests are the agents\' work '
    "while no agent call has failed. Call an agent with that step."
)

_NO_TOOL_NOTE = (
    'There is no JSON action "{verb}" and you have no tool for it. Call an agent, ask the user, or finish.'
)

_STEP_CLOSE_NOTE = (
    "You have used all {n} agent calls of this run; that call was not made. No more agent calls. "
    "Close now with finish: a short summary for the user of what is done and what is still open."
)

_IDLE_NOTE = (
    "You made {n} decisions in a row without progress: no agent call, no new tool result, no new user message. "
    "Act now: call an agent, ask the user, or finish. The run stops after {max} such decisions."
)

_FINISH_FILES_NOTE = (
    "A coding agent made no successful write or delete and returned no text. "
    "Check with a tool or call that agent again. Finish only when the files exist."
)


def _run_error_class(exc: BaseException) -> str:
    if isinstance(exc, turn_runtime.RunBudgetExceeded):
        return "budget"
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
        extra: dict[str, str] = {}
        try:
            if outcome == "succeeded":
                emit_log("info", "run.succeeded")
            elif outcome == "cancelled":
                emit_log("warn", "run.cancelled")
            else:
                emit_log("error", "run.failed")
            _emit_summary(ctrl, outcome, fail_exc)
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
        except Exception:
            # M5: a closed store or a full disk must not keep the run "running".
            log.exception("run end log failed run=%s", getattr(ctrl, "run_id", None))
        finally:
            ctrl.finish(outcome, **extra)

def _emit_summary(ctrl: RunController, outcome: str, fail_exc: BaseException | None) -> None:
    """B7: one line at the end with what the run did, for the log card and analyses."""
    stats = getattr(ctrl, "stats", None)
    if stats is None:
        return
    error = None
    if outcome == "failed":
        error = str(fail_exc) if fail_exc is not None else (ctrl.fail_message or None)
    emit_log("info", "run.summary", payload=stats.summary(outcome, error))

def _action_payload(
    compiled: CompiledGraph,
    names: list[tuple[str, str]],
    action: dict[str, str],
    kind: str,
    text: str,
    via: str,
) -> dict:
    """B2: what the orchestrator decided, readable without the memory."""
    from app.run.limits import LOG_TASK_MAX
    from app.run.log_payloads import clip

    payload: dict = {
        "action": kind,
        "agent": action.get("agent") or "",
        "requested": action.get("agentToken") or "",
        "via": via,
    }
    if kind == "call":
        agent_id = action.get("agent") or ""
        payload["agentName"] = dict(names).get(agent_id) or node_label(compiled, agent_id) or agent_id
        payload["task"] = clip((action.get("task") or "").strip(), LOG_TASK_MAX)
        if action.get("source"):
            payload["source"] = action.get("source") or ""
        if action.get("retry") == "1":
            payload["retry"] = True
    elif text.strip():
        payload["text"] = clip(text.strip(), LOG_TASK_MAX)
    return payload

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

def _fail_stuck(ctrl: RunController, node_id: str, decisions: int) -> str:
    emit_log("error", "run.orchestrator.stuck", node_id=node_id, payload={"decisions": decisions})
    ctrl.fail_message = "run.orchestrator.stuck"
    ctrl.fail_class = "orchestrator"
    ctrl.last_error_node_id = node_id
    turn_runtime._set_node(ctrl, node_id, "error", error="run.orchestrator.stuck")
    return "failed"

def _fail_unreadable(ctrl: RunController, node_id: str) -> str:
    ctrl.fail_message = "run.orchestrator.unreadable"
    ctrl.fail_class = "orchestrator"
    ctrl.last_error_node_id = node_id
    emit_log("error", "run.orchestrator.unreadable", node_id=node_id)
    turn_runtime._set_node(ctrl, node_id, "error", error="run.orchestrator.unreadable")
    return "failed"

_TOOL_AS_TEXT_NOTE = (
    "A tool call written as text does not run. Call a tool with a native tool call; "
    "the tools open on this turn are listed under Connected tools."
)


_OVER_BUDGET_NOTE = (
    "The tool steps you wrote as text did not run: the last decision had used all {n} tool calls. "
    "This decision has a new budget. Read only what is still missing, as tool calls, then decide: "
    "call an agent, ask, reply or finish."
)

def _tool_request_note(
    verb: str,
    memory: RunMemory,
    full_names: list[str],
    write_open: bool,
    open_names: list[str] | None = None,
) -> tuple[str, bool]:
    """The hint for a tool step written as text, and whether write access was opened."""
    if verb == "use":
        return _TOOL_AS_TEXT_NOTE, False
    if verb in WRITE_VERBS or verb in RUN_VERBS:
        tool = "terminal" if verb in RUN_VERBS else "file_access"
        if tool not in full_names:
            return _NO_TOOL_NOTE.format(verb=verb), False
        if write_open:
            return _NATIVE_TOOL_NOTE.format(verb=verb, tool=tool), False
        if memory.had_failure():
            memory.allow_own_tools = True
            return _SELF_TAKEOVER_NOTE.format(verb=verb), True
        return _WRITE_LOCKED_NOTE.format(verb=verb), False
    if "file_access" not in (open_names if open_names is not None else full_names):
        return _NO_TOOL_NOTE.format(verb=verb), False
    return _NATIVE_TOOL_NOTE.format(verb=verb, tool="file_access"), False

def _fail_think_loop(ctrl: RunController, node_id: str, thinks: int) -> str:
    emit_log("error", "run.orchestrator.thinkLoop", node_id=node_id, payload={"thinks": thinks})
    ctrl.fail_message = "run.orchestrator.thinkLoop"
    ctrl.fail_class = "orchestrator"
    ctrl.last_error_node_id = node_id
    turn_runtime._set_node(ctrl, node_id, "error", error="run.orchestrator.thinkLoop")
    return "failed"

def _chain_roots(compiled: CompiledGraph) -> list[str]:
    """Agents no other node hands a message to. They start a chain without a chat input."""
    fed = {edge.target for edge in compiled.doc.edges if edge.target_handle == "message"}
    roots = [agent_id for agent_id in compiled.topo_agents if agent_id not in fed]
    # A graph without a root cannot pass validation (cycle); keep the old start as a net.
    return roots or list(compiled.topo_agents)


def _step_input(payload: str, *, start: bool) -> list[LlmMessage]:
    """The one user message of a linear step: the text of its incoming edge (Paket 6, H8).

    Every step used to share one growing list, so the second agent read the answer of
    the first as its own assistant turn and the request ended on an assistant message.
    """
    text = (payload or "").strip()
    if not text:
        text = _BATCH_START if start else _EMPTY_HANDOFF
    return [LlmMessage(role="user", content=text)]


def _run_linear(ctrl: RunController, compiled: CompiledGraph, user_text: str) -> str:
    # (node, text of the incoming edge, True for a start node)
    pending: deque[tuple[str, str, bool]] = deque()
    if compiled.chat_input:
        for edge in compiled.doc.edges:
            if edge.source == compiled.chat_input.id:
                pending.append((edge.target, user_text or "", True))
    else:
        # Without a chat input only the roots start. Seeding every agent ran the later
        # ones twice, the first time before their input existed (M9).
        for agent_id in _chain_roots(compiled):
            pending.append((agent_id, user_text or "", True))
    end_hit: set[str] = set()
    invocations = 0
    while pending and not ctrl.stop_event.is_set():
        node_id, payload, start = pending.popleft()
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
            pending.append((target, payload, start))
            continue
        if node.type != "agent":
            continue
        invocations += 1
        if invocations > MAX_AGENT_INVOCATIONS:
            return _fail_step_limit(ctrl, node_id)
        text = agent_turn._agent_turn(
            ctrl, compiled, node_id, payload, _step_input(payload, start=start)
        )
        if text is None:
            if ctrl.stop_event.is_set():
                break
            if turn_runtime._user_aborted(ctrl):
                # M6: a chain has no conversation to return to; stopping it ends the run.
                emit_log("warn", "run.chat.aborted", node_id=node_id)
                turn_runtime._set_node(ctrl, node_id, "idle")
                return "cancelled"
            return "failed" if ctrl.fail_message else "cancelled"
        for target in compiled.agents[node_id].outbound_message:
            pending.append((target, text, False))
    if ctrl.stop_event.is_set():
        return "cancelled"
    if end_hit:
        return "succeeded"
    if not ctrl.fail_message:
        # N13: say why; the run used to fail here without any message.
        emit_log("error", "run.noEnd")
        ctrl.fail_message = "run.noEnd"
    return "failed"

def _run_orchestrator(ctrl: RunController, compiled: CompiledGraph, user_text: str) -> str:
    orch = compiled.orchestrator
    if orch is None:
        return "failed"
    memory = RunMemory()
    memory.miss_limit = orch.agent_miss_limit
    ctrl.llm_budget = orch.max_llm_calls
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
    # Reading and checking always; changing files after a failed agent call or in a takeover.
    full_tools = orch_tools.schemas(orch, write_open=True)
    read_tools = orch_tools.schemas(orch, write_open=False)
    full_names = turn_runtime._function_names(full_tools)
    later = orch_tools.later_labels(orch, read_tools, full_tools)
    tool_cap = orch.max_tool_calls or MAX_ORCHESTRATOR_TOOL_CALLS
    read_cap = orch.max_read_calls or MAX_READ_DECISION_CALLS
    step_cap = orch.max_agent_calls or MAX_ORCHESTRATOR_STEPS
    # At the step limit: decisions left for the closing summary (None until then).
    closing: int | None = None
    names = [(agent_id, name) for agent_id, name, _ in roster]
    steps = 0
    thinks = 0
    short_thinks = 0
    spoke = False
    pauses = 0
    # Decisions without progress, and unreadable decisions turned into a think after a reply.
    idle = 0
    unreadable = 0

    def _no_progress() -> str | None:
        nonlocal idle
        idle += 1
        if idle >= MAX_IDLE_DECISIONS:
            _store_memory(ctrl, memory)
            turn_runtime._set_llm(ctrl, compiled, orch.llm.node_id or orch.node_id, busy=False)
            return _fail_stuck(ctrl, orch.node_id, idle)
        if idle == IDLE_NUDGE_DECISIONS:
            memory.set_nudge(_IDLE_NOTE.format(n=idle, max=MAX_IDLE_DECISIONS))
        return None
    while not ctrl.stop_event.is_set():
        if turn_runtime._user_aborted(ctrl):
            # M6: "stop generating" in the chat; wait for the user's next message.
            reply = _wait_after_abort(ctrl, compiled)
            if reply is None:
                return "cancelled"
            memory.add_user(reply)
            spoke = False
            continue
        if _drain_user(ctrl, compiled, memory):
            # New user input: a reply to it is a fresh answer, not a second reply.
            spoke = False
            idle = 0
        write_open = memory.allow_own_tools or memory.takeover is not None
        offered = full_tools if write_open else read_tools
        if closing is not None:
            # Closing turn: no tools, only the summary.
            offered = []
        # Reading only (no failure yet): a small budget per decision. After a failure or
        # in a takeover the full per-decision cap applies.
        decision_cap = tool_cap if write_open else min(tool_cap, read_cap)
        orientation_left: int | None = None
        if not memory.records:
            # Looking around before the first agent call is short; then it must delegate.
            orientation_left = max(0, MAX_ORIENTATION_CALLS - memory.orientation_calls)
            decision_cap = min(decision_cap, orientation_left)
            if orientation_left == 0:
                offered = []
        offered = turn_runtime._available_tools(ctrl, compiled, orch.node_id, offered)
        system = orchestrator_instructions(
            orch.system_prompt,
            roster,
            turn_runtime._function_names(offered),
            takeover=memory.takeover is not None,
            write_open=write_open,
            tool_cap=decision_cap,
            tools_connected=bool(full_tools),
            later=later,
            orientation_left=orientation_left,
            capabilities=orchestrator_capabilities(compiled, orch.node_id, offered),
        )
        own_start = len(memory.own_tools)
        action = orchestrator_decide._orchestrator_action(
            ctrl,
            compiled,
            system,
            memory,
            offered,
            names,
            block_reply=spoke,
            write_open=write_open,
            tool_cap=decision_cap,
            orientation=orientation_left is not None,
        )
        tokens = orchestrator_decide._pop_tokens(action)
        # A new tool result is new information, also when the decision itself is a think.
        fresh = memory.mark_own_calls(own_start)
        if fresh:
            idle = 0
        _store_memory(ctrl, memory)
        if action is None:
            if ctrl.stop_event.is_set():
                return "cancelled"
            # M6: decide returns None only when the call was cancelled. Without Stop
            # that was the chat's "stop generating", even if a new message already
            # cleared the flag.
            reply = _wait_after_abort(ctrl, compiled)
            if reply is None:
                return "cancelled"
            memory.add_user(reply)
            spoke = False
            continue
        if action.get("action") == "failed-window":
            turn_runtime._set_node(ctrl, orch.node_id, "error", error="run.orchestrator.window")
            return "failed"
        if action.get("action") == "failed-tools":
            return "failed"
        if action.get("action") == "llm-unavailable":
            key = action.get("text") or "runtime.unreachable"
            pauses += 1
            if pauses > MAX_LLM_PAUSES:
                ctrl.fail_message = key
                ctrl.fail_class = "llm_error"
                ctrl.last_error_node_id = orch.node_id
                turn_runtime._set_node(ctrl, orch.node_id, "error", error=key)
                return "failed"
            reply = _pause_for_model(ctrl, compiled, key)
            if reply is None:
                return "cancelled"
            memory.add_user(reply)
            spoke = False
            continue
        if action.get("action") == "unreadable":
            return _fail_unreadable(ctrl, orch.node_id)
        if action.pop("_unreadable", None):
            # After a reply, an unreadable decision became a think. Twice in a row ends the run.
            unreadable += 1
            if unreadable >= MAX_UNREADABLE_STREAK:
                _store_memory(ctrl, memory)
                turn_runtime._set_llm(ctrl, compiled, orch.llm.node_id or orch.node_id, busy=False)
                return _fail_unreadable(ctrl, orch.node_id)
        else:
            unreadable = 0
        if closing is not None and action.get("action") in {"think", "defer", "tool-request"}:
            # Closing turn after the step limit: no planning rounds, only the summary.
            closing -= 1
            if closing <= 0:
                _store_memory(ctrl, memory)
                turn_runtime._set_llm(ctrl, compiled, orch.llm.node_id or orch.node_id, busy=False)
                return _fail_step_limit(ctrl, orch.node_id)
            memory.set_nudge(_STEP_CLOSE_NOTE.format(n=steps))
            continue
        if action.get("action") == "tool-request":
            verb = (action.get("verb") or "").strip().lower()
            over_budget = action.pop("_overBudget", None)
            note, granted = _tool_request_note(
                verb, memory, full_names, write_open, turn_runtime._function_names(offered)
            )
            if over_budget is not None:
                note = _OVER_BUDGET_NOTE.format(n=over_budget) + " " + note
            emit_log(
                "warn",
                "run.orchestrator.toolRequest",
                node_id=orch.node_id,
                payload={"verb": verb, "granted": granted, **({"overBudget": True} if over_budget is not None else {})},
            )
            if granted:
                emit_log("info", "run.orchestrator.selfTakeover", node_id=orch.node_id, payload={"verb": verb})
            turn_runtime._set_node(ctrl, orch.node_id, "running", wait="thinking")
            memory.set_nudge(note)
            if not fresh:
                stuck = _no_progress()
                if stuck:
                    return stuck
            continue
        if action.get("action") in {"think", "defer"}:
            blocked = action.pop("_blocked", None)
            body = (action.get("text") or "").strip()
            repeated = memory.add_think(body)
            if blocked:
                memory.set_nudge(_BLOCKED_REPLY_NOTE)
            elif repeated:
                memory.set_nudge(_REPEAT_THINK_NOTE)
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
            if not fresh:
                stuck = _no_progress()
                if stuck:
                    return stuck
            continue
        kind = action.get("action") or "reply"
        text = action.get("text") or ""
        action.pop("_blocked", None)
        via = action.pop("_via", None) or "json"
        if closing is not None:
            # The step limit was reached: a text is the summary, then the run ends as stepLimit.
            if kind in {"finish", "reply", "ask"} and text.strip():
                _publish_assistant(ctrl, text.strip())
                memory.add_spoken("finish", text.strip())
                _store_memory(ctrl, memory)
                return _fail_step_limit(ctrl, orch.node_id)
            closing -= 1
            if closing <= 0:
                _store_memory(ctrl, memory)
                return _fail_step_limit(ctrl, orch.node_id)
            memory.set_nudge(_STEP_CLOSE_NOTE.format(n=steps))
            continue
        memory.clear_nudge()
        emit_log(
            "info",
            "run.orchestrator.action",
            node_id=orch.node_id,
            payload=_action_payload(compiled, names, action, kind, text, via),
        )
        if kind == "ask":
            spoke = False
            thinks = 0
            short_thinks = 0
            if _drain_user(ctrl, compiled, memory):
                # Messages already queued are not the answer to a question the user never saw.
                memory.set_nudge(_ASK_SUPERSEDED_NOTE.format(question=(text or "").strip()[:300]))
                continue
            _speak(ctrl, compiled, memory, "ask", text or "…", wait=True)
            reply = _queue_get(ctrl)
            if not reply or ctrl.stop_event.is_set():
                return "cancelled"
            memory.add_user(reply)
            _clear_human_wait(ctrl, compiled)
            idle = 0
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
                if memory.takeover_rejects >= MAX_TAKEOVER_REJECTS:
                    _store_memory(ctrl, memory)
                    return _fail_takeover(ctrl, orch.node_id, memory)
                memory.add_note(
                    "That agent is closed for this task. "
                    "The connected tools can finish the file step. Do not call that agent again."
                )
                if not fresh:
                    stuck = _no_progress()
                    if stuck:
                        return stuck
                continue
            if steps >= step_cap:
                # One closing turn for a summary instead of ending without a word.
                emit_log("warn", "run.orchestrator.stepClose", node_id=orch.node_id, payload={"calls": steps})
                closing = 2
                memory.set_nudge(_STEP_CLOSE_NOTE.format(n=steps))
                _store_memory(ctrl, memory)
                continue
            outcome = dispatch._orchestrator_call(ctrl, compiled, memory, names, action, user_text)
            if outcome == "cancelled":
                return "cancelled"
            if memory.takeover_unarmed:
                # Anomaly instead of an instant failure; the run fails only after repeated cases.
                memory.takeover_unarmed = False
                memory.takeover_unavailable += 1
                emit_log(
                    "warn",
                    "run.orchestrator.takeoverUnavailable",
                    node_id=orch.node_id,
                    payload={"count": memory.takeover_unavailable, "max": MAX_TAKEOVER_UNAVAILABLE},
                )
                if memory.takeover_unavailable > MAX_TAKEOVER_UNAVAILABLE:
                    _store_memory(ctrl, memory)
                    return _fail_takeover(ctrl, orch.node_id, memory, no_tool=True)
                closed = memory.takeover
                if closed is not None:
                    memory.misses[closed.agent_id] = 0
                    memory.text_retry_fails[closed.agent_id] = 0
                memory.takeover = None
                memory.set_nudge(_TAKEOVER_UNAVAILABLE_NOTE)
            if outcome == "ran":
                steps += 1
                idle = 0
            elif not fresh:
                stuck = _no_progress()
                if stuck:
                    return stuck
            continue
        if kind == "finish":
            if memory.takeover:
                # O13: one warning first; a second finish ends the run honestly as failed.
                if not memory.takeover_finish_warned:
                    memory.takeover_finish_warned = True
                    memory.set_nudge(_TAKEOVER_FINISH_NOTE)
                    if not fresh:
                        stuck = _no_progress()
                        if stuck:
                            return stuck
                    continue
                _store_memory(ctrl, memory)
                return _fail_takeover(ctrl, orch.node_id, memory)
            if _drain_user(ctrl, compiled, memory):
                spoke = False
                idle = 0
                memory.set_nudge(_FINISH_LATE_NOTE)
                continue
            if _tool_work_unverified(memory) and not memory.finish_warned:
                memory.finish_warned = True
                memory.add_note(_FINISH_FILES_NOTE)
                if not fresh:
                    stuck = _no_progress()
                    if stuck:
                        return stuck
                continue
            if text.strip():
                _publish_assistant(ctrl, text.strip())
                memory.add_spoken("finish", text.strip())
            _finish_targets(ctrl, compiled, orch, text)
            _store_memory(ctrl, memory)
            return "succeeded"
        # O13: a reply during takeover informs the user; it no longer fails the run.
        if text.strip():
            _publish_assistant(ctrl, text.strip())
            memory.add_spoken("reply", text.strip())
        spoke = True
        # A reply is no progress: it no longer resets the think count (Dev Team run, 2026-11-16).
        short_thinks = 0
        if not fresh:
            stuck = _no_progress()
            if stuck:
                return stuck
        continue
    _store_memory(ctrl, memory)
    turn_runtime._set_llm(ctrl, compiled, orch.llm.node_id or orch.node_id, busy=False)
    return "cancelled"

def _drain_user(ctrl: RunController, compiled: CompiledGraph, memory: RunMemory) -> int:
    """Move chat messages sent while the orchestrator worked into the course.

    The queue used to be read only by ``ask``: mid-run messages went unseen, then
    answered the next question before the user saw it, or were lost on finish.
    """
    taken = 0
    while True:
        try:
            raw = ctrl.chat_input_queue.get_nowait()
        except queue.Empty:
            break
        cleaned = (raw or "").strip()
        if not cleaned:
            continue
        memory.add_user(cleaned)
        taken += 1
        emit_log(
            "info",
            "run.chat.user",
            node_id=compiled.chat_input.id if compiled.chat_input else None,
            payload={"chars": len(cleaned), "midRun": True},
        )
    return taken

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
    """Persist the course. O15: bounded payload, and no write when nothing changed."""
    if not ctrl.run_id:
        return
    import json

    payload = memory.to_dict()
    try:
        fingerprint = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        fingerprint = None
    if fingerprint is not None and fingerprint == memory.persisted:
        return
    try:
        from app.db.runs import update_run

        update_run(ctrl.run_id, memory=payload)
        memory.persisted = fingerprint
    except Exception:
        log.warning("run memory not stored run=%s", ctrl.run_id, exc_info=True)

def _pause_for_model(ctrl: RunController, compiled: CompiledGraph, key: str) -> str | None:
    """O14: tell the user the orchestrator model is away and wait for a message to retry."""
    orch = compiled.orchestrator
    node_id = orch.node_id if orch is not None else None
    msg = ChatMessage(
        id=str(uuid.uuid4()),
        run_id=ctrl.run_id or "",
        role="assistant",
        content="The orchestrator model is not reachable right now. Send a message to try again.",
        created_at=utc_now(),
        message_key="monitoring.chat.llmRetry",
        message_params={"error": key},
    )
    ctrl.remember_chat(msg, generating=False)
    speaker = node_label(compiled, node_id) or "orchestrator"
    ctrl.set_wait_ask(speaker=speaker, excerpt=msg.content, node_id=node_id)
    if node_id:
        turn_runtime._set_node(ctrl, node_id, "waiting", wait="human")
    emit_log("warn", "run.orchestrator.llmPause", node_id=node_id, payload={"error": key})
    reply = _queue_get(ctrl)
    _clear_human_wait(ctrl, compiled)
    if not reply or ctrl.stop_event.is_set():
        return None
    return reply

def _wait_after_abort(ctrl: RunController, compiled: CompiledGraph) -> str | None:
    """M6: say that generation stopped, then wait for the next user message."""
    orch = compiled.orchestrator
    node_id = orch.node_id if orch is not None else None
    emit_log("warn", "run.chat.aborted", node_id=node_id)
    if orch is not None:
        turn_runtime._set_llm(ctrl, compiled, orch.llm.node_id or orch.node_id, busy=False)
    for agent_id in compiled.agents:
        runtime = ctrl.snapshot.nodes_runtime.get(agent_id) if ctrl.snapshot else None
        if runtime is not None and runtime.status == "running":
            turn_runtime._set_node(ctrl, agent_id, "idle")
    msg = ChatMessage(
        id=str(uuid.uuid4()),
        run_id=ctrl.run_id or "",
        role="assistant",
        content="Stopped. Send a message to continue.",
        created_at=utc_now(),
        message_key="monitoring.chat.aborted",
    )
    ctrl.remember_chat(msg, generating=False)
    speaker = node_label(compiled, node_id) or "orchestrator"
    ctrl.set_wait_ask(speaker=speaker, excerpt=msg.content, node_id=node_id)
    _wait_chat(ctrl, compiled)
    reply = _queue_get(ctrl)
    ctrl.abort_generation.clear()
    _clear_human_wait(ctrl, compiled)
    if not reply or ctrl.stop_event.is_set():
        return None
    return reply


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

