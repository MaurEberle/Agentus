"""Orchestrator envelope for one agent, and the report written back into the book."""

from __future__ import annotations

import uuid

from app.db.engine import utc_now
from app.run import agent_turn, turn_runtime
from app.run.compile import CompiledGraph
from app.run.controller import RunController, emit_log
from app.run.limits import MAX_SAME_RETRIES, MAX_TEXT_RETRIES
from app.run.memory import AgentRecord, RunMemory, Takeover, visible_text
from app.run.models import ChatMessage
from app.run.orchestrate import match_agent
from app.run.turn_runtime import _FILE_MUTATIONS, _SAME_RETRY
from app.runtime.models import ChatMessage as LlmMessage

def _unknown_agent_note(token: str, names: list[tuple[str, str]]) -> str:
    roster = ", ".join(f"{name} ({agent_id})" for agent_id, name in names)
    return f"Unknown agent: {token}. Use a name or id from the roster: {roster}."

def _source_repair_note(source, memory: RunMemory) -> str:
    if source.ambiguous:
        return "Source is ambiguous. Set source to one id: " + ", ".join(source.ambiguous)
    last = ""
    for rec in memory.records:
        if rec.finished and rec.text:
            last = rec.agent_id
    hint = f" Last stored text is from {last}." if last else ""
    return f"Unknown source: {source.missing}.{hint} Omit source to send only the task."

def _count_file_attempt(
    compiled: CompiledGraph,
    memory: RunMemory,
    agent,
    record: AgentRecord,
) -> None:
    if "file_access" not in (agent.tool_kinds or []):
        return
    wrote = any(fact.ok and fact.action in _FILE_MUTATIONS for fact in record.files)
    # A finished text answer that never touched a file is the result, not a missed write.
    if record.finished and record.text and not record.files:
        return
    opened = memory.note_file_attempt(
        agent_id=agent.node_id,
        name=record.name,
        task=record.task,
        wrote=wrote,
    )
    if not opened:
        return
    orch = compiled.orchestrator
    if orch is None or "file_access" not in (orch.tool_kinds or []):
        memory.takeover_unarmed = True
        return
    emit_log(
        "info",
        "run.orchestrator.takeoverStart",
        node_id=orch.node_id,
        payload={
            "agent": record.name,
            "misses": memory.misses.get(agent.node_id, 0),
            "task": (record.task or "")[:300],
        },
    )

def _review_text_retry(compiled: CompiledGraph, memory: RunMemory, agent, record: AgentRecord) -> None:
    """Count a retry that again came back as text only; open a tools takeover at the limit."""
    agent_id = agent.node_id
    if not record.text_only:
        memory.text_retry_fails[agent_id] = 0
        return
    fails = memory.text_retry_fails.get(agent_id, 0) + 1
    memory.text_retry_fails[agent_id] = fails
    emit_log(
        "warn",
        "run.orchestrator.textRetry",
        node_id=agent_id,
        payload={"name": record.name, "fails": fails, "max": MAX_TEXT_RETRIES},
    )
    if fails < MAX_TEXT_RETRIES or memory.takeover is not None:
        return
    orch = compiled.orchestrator
    if orch is None or not (orch.tool_kinds or orch.mcp):
        # No takeover possible: the loop reports an anomaly; the next round counts afresh.
        memory.takeover_unarmed = True
        memory.text_retry_fails[agent_id] = 0
        return
    memory.takeover = Takeover(agent_id=agent_id, name=record.name, task=record.task, kind="tools")
    memory.takeover_rejects = 0
    emit_log(
        "info",
        "run.orchestrator.takeoverStart",
        node_id=orch.node_id,
        payload={"agent": record.name, "misses": fails, "task": (record.task or "")[:300], "kind": "tools"},
    )

def _orchestrator_call(
    ctrl: RunController,
    compiled: CompiledGraph,
    memory: RunMemory,
    names: list[tuple[str, str]],
    action: dict[str, str],
    user_text: str,
) -> str:
    token = action.get("agent") or ""
    agent_id = match_agent(token, names)
    given_task = (action.get("task") or "").strip()
    task = given_task or memory.last_user() or user_text
    if agent_id is None or agent_id not in compiled.agents:
        memory.add_note(_unknown_agent_note(token, names))
        return "skipped"
    if not given_task:
        # O17: an empty task falls back to the last user message; make that visible.
        emit_log("warn", "run.orchestrator.emptyTask", node_id=agent_id)
    agent = compiled.agents[agent_id]
    has_tools = bool(agent.tool_kinds or agent.mcp)
    source = memory.resolve_source(action.get("source") or "", names)
    if source.ambiguous or source.missing:
        memory.add_note(_source_repair_note(source, memory))
        return "skipped"
    if source.auto:
        emit_log("info", "run.memory.source", node_id=agent_id)
    name = dict(names).get(agent_id, agent_id)
    previous = next((rec for rec in reversed(memory.records) if rec.agent_id == agent_id), None)
    # Text-only review (variant C): only an explicit retry of a text-only answer counts.
    is_text_retry = action.get("retry") == "1" and previous is not None and previous.text_only
    if action.get("retry") == "1" and not is_text_retry:
        emit_log("info", "run.orchestrator.retryIgnored", node_id=agent_id)
    if not is_text_retry:
        memory.text_retry_fails[agent_id] = 0
    record = memory.begin_call(agent_id, name, task, has_tools)
    record.retry = is_text_retry
    memory.allow_own_tools = False

    def _ran() -> str:
        _count_file_attempt(compiled, memory, agent, record)
        if is_text_retry:
            _review_text_retry(compiled, memory, agent, record)
        return "ran"

    orch = compiled.orchestrator
    if orch is not None:
        turn_runtime._set_node(ctrl, orch.node_id, "waiting")
    delivered = memory.agent_message(agent_id, task, has_tools, source.text)
    attempt = 0
    continued = False
    while not ctrl.stop_event.is_set():
        text = agent_turn._agent_turn(
            ctrl,
            compiled,
            agent_id,
            task,
            [LlmMessage(role="user", content=delivered)],
            publish_chat=False,
            memory=memory,
            record=record,
            reuse=continued,
        )
        if text is None:
            if ctrl.stop_event.is_set():
                return "cancelled"
            # O17: the agent turn gave up without a result; tell the orchestrator why.
            record.error = record.error or "agent stopped"
            memory.allow_own_tools = True
            memory.set_anomaly(record)
            return _ran()
        if record.error == "prompt does not fit":
            memory.allow_own_tools = True
            memory.set_anomaly(record)
            return _ran()
        if record.error == "too many tool failures":
            memory.allow_own_tools = True
            memory.set_anomaly(record)
            return _ran()
        if record.error in {"too many thinks", "think loop", "empty stops", "runtime.generationLimit", "output limit"}:
            memory.allow_own_tools = True
            memory.set_anomaly(record)
            return _ran()
        if record.error:
            if record.tool_ok and not continued:
                continued = True
                record.error = ""
                delivered = memory.continuation_message(agent_id, task, has_tools, source.text)
                continue
            if (
                not record.tool_ok
                and not record.saw_tokens
                and record.error in _SAME_RETRY
                and attempt < MAX_SAME_RETRIES
            ):
                attempt += 1
                record.error = ""
                continue
            memory.allow_own_tools = True
            memory.set_anomaly(record)
            return _ran()
        visible = visible_text(text or "")
        if text and not visible:
            memory.reject(text, "empty")
        wrote = any(fact.ok and fact.action in _FILE_MUTATIONS for fact in record.files)
        if not visible and not record.tool_ok:
            record.error = "empty result"
            memory.allow_own_tools = True
            memory.set_anomaly(record)
            return _ran()
        record.text = visible
        if not visible and not wrote:
            record.error = "empty result"
            emit_log("warn", "run.agent.empty", node_id=agent_id)
            memory.allow_own_tools = True
            memory.set_anomaly(record)
            return _ran()
        record.finished = True
        if has_tools and not record.tools and visible:
            # Allowed: tools are optional. The orchestrator checks the text against the task.
            record.text_only = True
            emit_log("info", "run.agent.textOnly", node_id=agent_id)
        if any(not fact.ok for fact in record.files):
            record.error = "tool failed"
            memory.set_anomaly(record)
        else:
            _publish_progress(ctrl, name, record)
            memory.add_note(f"Status already shown to the user: {name} finished.")
        return _ran()
    return "cancelled"

def _publish_progress(ctrl: RunController, name: str, record: AgentRecord) -> None:
    files = [fact for fact in record.files if fact.ok and fact.path]
    if files:
        shown = ", ".join(f"{fact.path} {fact.action}" for fact in files[:8])
        key = "monitoring.chat.agentDoneFiles"
        params = {"name": name, "files": shown}
        content = f"{name} is done. Files: {shown}."
    else:
        key = "monitoring.chat.agentDone"
        params = {"name": name}
        content = f"{name} is done."
    msg = ChatMessage(
        id=str(uuid.uuid4()),
        run_id=ctrl.run_id or "",
        role="assistant",
        content=content,
        created_at=utc_now(),
        message_key=key,
        message_params=params,
    )
    ctrl.remember_chat(msg, generating=False)

