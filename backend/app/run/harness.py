from __future__ import annotations

import json
import traceback
import time
import uuid
from collections import deque

from app.common.secrets import mask_obj
from app.db.engine import utc_now
from app.db.runs import insert_call, upsert_step
from app.db.vault import get as vault_get
from app.run.compile import CompiledGraph
from app.run.controller import RunController, emit_log, node_label
from app.run.knowledge import retrieve
from app.run.limits import (
    DEFAULT_SCORE_MIN,
    DEFAULT_TOP_K,
    MAX_AGENT_INVOCATIONS,
    MAX_ORCHESTRATOR_STEPS,
    MAX_TOOL_ROUNDS,
    STREAM_IDLE_TIMEOUT_SEC,
)
from app.run.orchestrate import (
    looks_like_control,
    match_agent,
    orchestrator_instructions,
    parse_orchestrator_action,
)
from app.run.mcp_bridge import get_mcp, map_openai_tool_name
from app.run.models import ActivityTokens, ChatMessage, NodeRuntime, NodeTokens
from app.run.sse import publish
from app.runtime.errors import RuntimeApiError
from app.runtime.completions import estimate_token_count
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import CompletionRequest, CompletionResult

_ORCHESTRATOR_REPAIR = (
    "That message was not one valid JSON object. It was not shown to the user and no agent was called. "
    "Reply with one JSON object only. The task must be a short instruction. "
    "Do not paste the previous agent result into the task. It is attached automatically."
)
from app.tools.catalog import openai_tools_for_kinds
from app.tools import execute as tools_execute


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
        if compiled.orchestrator is not None:
            outcome = _run_orchestrator(ctrl, compiled, user_text or "")
        else:
            outcome = _run_linear(ctrl, compiled, user_text or "")
    except Exception as exc:
        fail_exc = exc
        emit_log("error", str(exc), stack=traceback.format_exc())
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
        _set_node(ctrl, chat.id, "waiting", wait="human")
        emit_log("info", "run.wait.human", node_id=chat.id)
        return _queue_get(ctrl)
    if start:
        if compiled.chat_input:
            _publish_user(ctrl, start)
        return start
    _set_node(ctrl, chat.id, "waiting", wait="human")
    emit_log("info", "run.wait.human", node_id=chat.id)
    return _queue_get(ctrl)


def _queue_get(ctrl: RunController) -> str | None:
    while not ctrl.stop_event.is_set():
        try:
            return ctrl.chat_input_queue.get(timeout=0.2)
        except Exception:
            continue
    return None


def _route(compiled: CompiledGraph, router_id: str, text: str) -> str | None:
    line = text.splitlines()[0].strip() if text else ""
    edges = compiled.routers.get(router_id) or []
    for handle, target in edges:
        if handle == line:
            return target
    for handle, target in edges:
        if handle == "default":
            return target
    return edges[0][1] if edges else None


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
            _set_node(ctrl, node_id, "done")
            emit_log("debug", "run.end", node_id=node_id)
            continue
        if node.type == "router":
            target = _route(compiled, node_id, payload)
            if target is None:
                emit_log("error", "graph.router.noEdge", node_id=node_id)
                return "failed"
            emit_log(
                "info",
                "run.router",
                node_id=node_id,
                payload={"target": target},
            )
            pending.append((target, payload))
            continue
        if node.type != "agent":
            continue
        invocations += 1
        if invocations > MAX_AGENT_INVOCATIONS:
            emit_log("error", "run.stepLimit", node_id=node_id)
            return "failed"
        text = _agent_turn(ctrl, compiled, node_id, payload, conversation)
        if text is None:
            if ctrl.stop_event.is_set():
                break
            continue
        for target in compiled.agents[node_id].outbound_message:
            pending.append((target, text))
    if ctrl.stop_event.is_set():
        return "cancelled"
    if end_hit:
        return "succeeded"
    return "failed"


def _agent_turn(
    ctrl: RunController,
    compiled: CompiledGraph,
    agent_id: str,
    user_text: str,
    conversation: list[LlmMessage],
    *,
    publish_chat: bool = True,
) -> str | None:
    agent = compiled.agents[agent_id]
    _set_node(ctrl, agent_id, "running", wait="llm")
    emit_log("info", "run.agent.start", node_id=agent_id)
    snippets: list[str] = []
    for kid in agent.knowledge_node_ids:
        node = compiled.by_id.get(kid)
        top_k = int(node.data.get("topK") or DEFAULT_TOP_K) if node else DEFAULT_TOP_K
        score_min = float(node.data.get("scoreThreshold") or DEFAULT_SCORE_MIN) if node else DEFAULT_SCORE_MIN
        for snip in retrieve(
            compiled.network_id,
            kid,
            user_text or " ",
            top_k=top_k,
            score_min=score_min,
            node=compiled.by_id.get(kid),
        ):
            label = f"{snip.title}#{snip.section}" if snip.section else snip.title
            snippets.append(f"- [{label}] {snip.text}")
    if agent.knowledge_node_ids:
        emit_log(
            "debug",
            "run.knowledge",
            node_id=agent_id,
            payload={"count": len(snippets)},
        )
    context = "\n".join(snippets) if snippets else "No document context."
    system = (agent.system_prompt + "\n\n# Document context\n" + context).strip()
    tools = openai_tools_for_kinds(agent.tool_kinds)
    mcp = get_mcp()
    if mcp and agent.mcp:
        from app.db.settings import get_mcp_server
        from app.mcp.models import McpToolInfo
        from app.run.mcp_bridge import mcp_openai_tools

        for server_id, allow in agent.mcp:
            row = get_mcp_server(server_id) or {}
            cached = row.get("cached_tools") or []
            infos = [
                McpToolInfo(
                    name=str(t.get("name")),
                    description=t.get("description"),
                    input_schema=t.get("input_schema") or {},
                )
                for t in cached
                if isinstance(t, dict) and t.get("name")
            ]
            if allow:
                infos = [i for i in infos if i.name in allow]
            tools.extend(mcp_openai_tools(server_id, infos))
    secret = None
    if agent.llm.provider != "ollama" and agent.llm.credential_id:
        secret = vault_get(agent.llm.credential_id)
    messages = [LlmMessage(role="system", content=system), *conversation]
    from app.runtime import completions as runtime_completions

    rounds = 0
    content = ""
    llm_node_id = agent.llm.node_id or agent_id
    while rounds <= MAX_TOOL_ROUNDS:
        started = time.perf_counter()
        emit_log(
            "info",
            "run.llm.start",
            node_id=llm_node_id,
            payload={
                "provider": agent.llm.provider,
                "model": agent.llm.model,
                "waitReason": "llm",
            },
        )
        try:
            result: CompletionResult = runtime_completions.complete_live(
                CompletionRequest(
                    provider=agent.llm.provider,  # type: ignore[arg-type]
                    model=agent.llm.model,
                    messages=messages,
                    base_url=agent.llm.base_url,
                    credential_id=agent.llm.credential_id,
                    secret=secret,
                    temperature=agent.llm.temperature,
                    max_tokens=agent.llm.max_tokens,
                    tools=tools or None,
                    timeout_sec=STREAM_IDLE_TIMEOUT_SEC,
                ),
                should_abort=ctrl.stop_event.is_set,
                on_progress=lambda out, rate: _publish_tokens(
                    ctrl,
                    agent_id,
                    llm_node_id,
                    tokens_in=None,
                    tokens_out=out,
                    per_second=rate,
                    committed=False,
                ),
            )
            ok = True
        except Exception as exc:
            if isinstance(exc, RuntimeApiError) and (
                exc.error_key == "run.cancelled" or ctrl.stop_event.is_set()
            ):
                return None
            ctrl.last_error_node_id = agent_id
            emit_log("error", str(exc), node_id=agent_id, stack=traceback.format_exc())
            _set_node(ctrl, agent_id, "error", error=str(exc))
            insert_call(
                run_id=ctrl.run_id or "",
                provider=agent.llm.provider,
                model=agent.llm.model,
                ok=False,
                node_id=agent_id,
                node_name=node_label(compiled, agent_id),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            raise
        duration_ms = int((time.perf_counter() - started) * 1000)
        usage = result.usage
        if usage:
            out_final = usage.completion_tokens
            in_final = usage.prompt_tokens
        elif result.content:
            out_final = estimate_token_count(result.content)
            in_final = None
        else:
            out_final = None
            in_final = None
        rate_final = None
        if out_final is not None and duration_ms > 0:
            rate_final = out_final / max(duration_ms / 1000.0, 0.05)
        _publish_tokens(
            ctrl,
            agent_id,
            llm_node_id,
            tokens_in=in_final,
            tokens_out=out_final,
            per_second=rate_final,
            committed=True,
        )
        insert_call(
            run_id=ctrl.run_id or "",
            provider=agent.llm.provider,
            model=agent.llm.model,
            ok=ok,
            node_id=agent_id,
            node_name=node_label(compiled, agent_id),
            duration_ms=duration_ms,
            tokens_in=in_final,
            tokens_out=out_final,
        )
        emit_log(
            "debug",
            "run.llm.done",
            node_id=llm_node_id,
            payload={
                "model": agent.llm.model,
                "durationMs": duration_ms,
                "tokensIn": usage.prompt_tokens if usage else None,
                "tokensOut": usage.completion_tokens if usage else None,
            },
        )
        if result.tool_calls and rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            _set_node(ctrl, agent_id, "running", wait="tool")
            messages.append(
                LlmMessage(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls,
                )
            )
            for call in result.tool_calls:
                tool_node_id = agent_id
                mapped = map_openai_tool_name(call.name)
                if mapped and mcp:
                    out = mcp.call(mapped[0], mapped[1], _parse_args(call.arguments))
                    tool_result = out.get("result") if out.get("ok") else out
                elif call.name in agent.tool_kinds:
                    cred = None
                    for edge in compiled.doc.edges:
                        if edge.target == agent_id and edge.target_handle == "tool":
                            tool_node = compiled.by_id.get(edge.source)
                            if tool_node and str(tool_node.data.get("kind")) == call.name:
                                tool_node_id = tool_node.id
                                cid = tool_node.data.get("credentialId")
                                if cid:
                                    cred = vault_get(str(cid))
                                out = tools_execute.execute_first_party(
                                    call.name,
                                    config=tool_node.data,
                                    args=_parse_args(call.arguments),
                                    secret=cred,
                                )
                                tool_result = out.model_dump(by_alias=True)
                                break
                    else:
                        tool_result = {"ok": False, "error": "unknown tool"}
                else:
                    tool_result = {"ok": False, "error": f"unknown tool {call.name}"}
                ok_tool = True
                if isinstance(tool_result, dict) and tool_result.get("ok") is False:
                    ok_tool = False
                emit_log(
                    "info" if ok_tool else "warn",
                    "run.tool.call",
                    node_id=tool_node_id,
                    payload={"name": call.name, "waitReason": "tool", "ok": ok_tool},
                )
                messages.append(
                    LlmMessage(
                        role="tool",
                        content=str(mask_obj(tool_result)),
                        tool_call_id=call.id,
                    )
                )
            continue
        content = result.content or ""
        break
    _set_node(ctrl, agent_id, "done")
    emit_log("info", "run.agent.done", node_id=agent_id)
    if publish_chat and compiled.chat_input and content:
        msg = ChatMessage(
            id=str(uuid.uuid4()),
            run_id=ctrl.run_id or "",
            role="assistant",
            content=content,
            created_at=utc_now(),
        )
        ctrl.remember_chat(msg, generating=False)
        conversation.append(LlmMessage(role="assistant", content=content))
    return content


def _parse_args(raw: str) -> dict:
    import json

    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def _publish_tokens(
    ctrl: RunController,
    agent_id: str,
    llm_node_id: str,
    *,
    tokens_in: int | None,
    tokens_out: int | None,
    per_second: float | None,
    committed: bool,
) -> None:
    if not ctrl.snapshot:
        return
    live_out = 0 if tokens_out is None else tokens_out
    live_in = 0 if tokens_in is None else tokens_in
    if committed:
        if tokens_out is not None:
            ctrl.tokens_out += tokens_out
        if tokens_in is not None:
            ctrl.tokens_in += tokens_in
        run_out = ctrl.tokens_out
        run_in = ctrl.tokens_in
        rate = None
    else:
        run_out = ctrl.tokens_out + live_out
        run_in = ctrl.tokens_in + live_in
        rate = per_second
    node_tokens = NodeTokens(
        in_=tokens_in,
        out=tokens_out,
        per_second=rate,
    )
    runtime = dict(ctrl.snapshot.nodes_runtime)
    for nid in {agent_id, llm_node_id}:
        current = runtime.get(nid, NodeRuntime())
        runtime[nid] = current.model_copy(update={"tokens": node_tokens})
    activity = ctrl.snapshot.activity.model_copy(
        update={
            "tokens": ActivityTokens(
                in_=run_in or None,
                out=run_out,
                per_second=rate,
            )
        }
    )
    ctrl.snapshot = ctrl.snapshot.model_copy(update={"nodes_runtime": runtime, "activity": activity})
    publish("run", ctrl.snapshot.model_dump(by_alias=True))


def _set_node(
    ctrl: RunController,
    node_id: str,
    status: str,
    *,
    wait: str | None = None,
    error: str | None = None,
) -> None:
    if not ctrl.snapshot:
        return
    runtime = dict(ctrl.snapshot.nodes_runtime)
    current = runtime.get(node_id, NodeRuntime())
    runtime[node_id] = current.model_copy(
        update={"status": status, "wait_reason": wait, "error": error}
    )
    ctrl.snapshot = ctrl.snapshot.model_copy(update={"nodes_runtime": runtime})
    node = ctrl.compiled.by_id.get(node_id) if ctrl.compiled else None
    upsert_step(
        run_id=ctrl.run_id or "",
        node_id=node_id,
        node_name=node_label(ctrl.compiled, node_id),
        role=str(node.data.get("role") or "").strip() or None if node else None,
        type=node.type if node else None,
        status=status,
        wait_reason=wait,
        error_message=error,
    )
    publish("run", ctrl.snapshot.model_dump(by_alias=True))


def _run_orchestrator(ctrl: RunController, compiled: CompiledGraph, user_text: str) -> str:
    orch = compiled.orchestrator
    if orch is None:
        return "failed"
    history: list[LlmMessage] = []
    if user_text:
        history.append(LlmMessage(role="user", content=user_text))
    roster: list[tuple[str, str, str]] = []
    for agent_id in orch.agents:
        node = compiled.by_id.get(agent_id)
        name = agent_id
        instructions = ""
        if node is not None:
            name = str(node.data.get("displayName") or node.data.get("role") or agent_id).strip() or agent_id
            instructions = str(node.data.get("systemPrompt") or "")
        roster.append((agent_id, name, instructions))
    system = orchestrator_instructions(orch.system_prompt, roster)
    names = [(agent_id, name) for agent_id, name, _ in roster]
    steps = 0
    repairs = 0
    previous = ""
    while not ctrl.stop_event.is_set():
        steps += 1
        if steps > MAX_ORCHESTRATOR_STEPS:
            emit_log("error", "run.stepLimit", node_id=orch.node_id)
            return "failed"
        action = _orchestrator_action(ctrl, compiled, system, history)
        if action is None:
            return "cancelled" if ctrl.stop_event.is_set() else "failed"
        kind = action.get("action") or "reply"
        text = action.get("text") or ""
        if kind == "reply" and looks_like_control(text):
            repairs += 1
            emit_log("info", "run.orchestrator.repair", node_id=orch.node_id)
            history.append(LlmMessage(role="assistant", content=text[:400]))
            if repairs <= 2:
                history.append(LlmMessage(role="user", content=_ORCHESTRATOR_REPAIR))
                continue
            _speak(
                ctrl,
                compiled,
                "Ich konnte den nächsten Schritt nicht lesen. Sag kurz, wie es weitergehen soll.",
                history,
                wait=True,
            )
            reply = _queue_get(ctrl)
            if not reply or ctrl.stop_event.is_set():
                return "cancelled"
            history.append(LlmMessage(role="user", content=reply))
            repairs = 0
            continue
        repairs = 0
        if kind == "ask":
            _speak(ctrl, compiled, text or "…", history, wait=True)
            reply = _queue_get(ctrl)
            if not reply or ctrl.stop_event.is_set():
                return "cancelled"
            history.append(LlmMessage(role="user", content=reply))
            continue
        if kind == "call":
            token = action.get("agent") or ""
            agent_id = match_agent(token, names)
            task = (action.get("task") or text or user_text).strip()
            if agent_id is None or agent_id not in compiled.agents:
                history.append(LlmMessage(role="user", content=f"Unknown agent: {token}. Use an id from the roster."))
                continue
            delivered = task or user_text or " "
            if previous and previous not in delivered:
                delivered = f"{delivered}\n\nPrevious agent result:\n{previous}"
            history.append(
                LlmMessage(
                    role="assistant",
                    content=json.dumps(
                        {"action": "call", "agent": agent_id, "task": task},
                        ensure_ascii=False,
                    ),
                )
            )
            result = _agent_turn(
                ctrl,
                compiled,
                agent_id,
                task,
                [LlmMessage(role="user", content=delivered)],
                publish_chat=False,
            )
            if result is None:
                if ctrl.stop_event.is_set():
                    return "cancelled"
                history.append(LlmMessage(role="user", content=f"Agent {agent_id} produced no result."))
                continue
            previous = result
            preview = result.strip()
            history.append(
                LlmMessage(
                    role="user",
                    content=(
                        f"Result from {agent_id} is stored ({len(preview)} characters) and will be attached "
                        "to the next agent automatically. Do not paste it into the task.\n"
                        f"Preview:\n{preview[:800]}"
                    ),
                )
            )
            continue
        if kind == "finish":
            if text.strip():
                _publish_assistant(ctrl, text.strip())
            for target in orch.finals:
                node = compiled.by_id.get(target)
                if node is None:
                    continue
                if node.type == "end":
                    _set_node(ctrl, target, "done")
                    emit_log("debug", "run.end", node_id=target)
                elif node.type == "router":
                    nxt = _route(compiled, target, text)
                    end = compiled.by_id.get(nxt or "")
                    if end is not None and end.type == "end":
                        _set_node(ctrl, end.id, "done")
                        emit_log("debug", "run.end", node_id=end.id)
            _set_node(ctrl, orch.node_id, "done")
            if compiled.chat_input:
                _set_node(ctrl, compiled.chat_input.id, "done")
            return "succeeded"
        if text.strip():
            _publish_assistant(ctrl, text.strip())
            history.append(LlmMessage(role="assistant", content=text.strip()))
        _wait_chat(ctrl, compiled)
        reply = _queue_get(ctrl)
        if not reply or ctrl.stop_event.is_set():
            return "cancelled"
        history.append(LlmMessage(role="user", content=reply))
    return "cancelled"


def _speak(
    ctrl: RunController,
    compiled: CompiledGraph,
    text: str,
    history: list[LlmMessage],
    *,
    wait: bool,
) -> None:
    _publish_assistant(ctrl, text)
    history.append(LlmMessage(role="assistant", content=text))
    if wait:
        _wait_chat(ctrl, compiled)


def _wait_chat(ctrl: RunController, compiled: CompiledGraph) -> None:
    orch = compiled.orchestrator
    if orch is not None:
        _set_node(ctrl, orch.node_id, "waiting", wait="human")
    if compiled.chat_input:
        _set_node(ctrl, compiled.chat_input.id, "waiting", wait="human")
    emit_log("info", "run.wait.human", node_id=orch.node_id if orch else None)


def _orchestrator_action(
    ctrl: RunController,
    compiled: CompiledGraph,
    system: str,
    history: list[LlmMessage],
) -> dict[str, str] | None:
    orch = compiled.orchestrator
    if orch is None:
        return None
    _set_node(ctrl, orch.node_id, "running", wait="llm")
    ctrl.flush_chat(generating=True)
    llm = orch.llm
    secret = None
    if llm.provider != "ollama" and llm.credential_id:
        secret = vault_get(llm.credential_id)
    started = time.perf_counter()
    llm_node_id = llm.node_id or orch.node_id
    emit_log(
        "info",
        "run.llm.start",
        node_id=llm_node_id,
        payload={"provider": llm.provider, "model": llm.model, "waitReason": "llm"},
    )
    from app.runtime import completions as runtime_completions

    try:
        result = runtime_completions.complete_live(
            CompletionRequest(
                provider=llm.provider,  # type: ignore[arg-type]
                model=llm.model,
                messages=[LlmMessage(role="system", content=system), *history],
                base_url=llm.base_url,
                credential_id=llm.credential_id,
                secret=secret,
                temperature=llm.temperature,
                max_tokens=llm.max_tokens,
                timeout_sec=STREAM_IDLE_TIMEOUT_SEC,
            ),
            should_abort=ctrl.stop_event.is_set,
            on_progress=lambda out, rate: _publish_tokens(
                ctrl,
                orch.node_id,
                llm_node_id,
                tokens_in=None,
                tokens_out=out,
                per_second=rate,
                committed=False,
            ),
        )
    except Exception as exc:
        if isinstance(exc, RuntimeApiError) and (
            exc.error_key == "run.cancelled" or ctrl.stop_event.is_set()
        ):
            return None
        ctrl.last_error_node_id = orch.node_id
        emit_log("error", str(exc), node_id=orch.node_id, stack=traceback.format_exc())
        _set_node(ctrl, orch.node_id, "error", error=str(exc))
        raise
    duration_ms = int((time.perf_counter() - started) * 1000)
    usage = result.usage
    out_final = usage.completion_tokens if usage else (
        estimate_token_count(result.content) if result.content else None
    )
    in_final = usage.prompt_tokens if usage else None
    rate_final = None
    if out_final is not None and duration_ms > 0:
        rate_final = out_final / max(duration_ms / 1000.0, 0.05)
    _publish_tokens(
        ctrl,
        orch.node_id,
        llm_node_id,
        tokens_in=in_final,
        tokens_out=out_final,
        per_second=rate_final,
        committed=True,
    )
    insert_call(
        run_id=ctrl.run_id or "",
        provider=llm.provider,
        model=llm.model,
        ok=True,
        node_id=orch.node_id,
        node_name=node_label(compiled, orch.node_id),
        duration_ms=duration_ms,
        tokens_in=in_final,
        tokens_out=out_final,
    )
    return parse_orchestrator_action(result.content or "")


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
