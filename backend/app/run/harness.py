from __future__ import annotations

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
    MAX_CONTROL_REPAIRS,
    MAX_ORCHESTRATOR_STEPS,
    MAX_ORCHESTRATOR_TOOL_ROUNDS,
    MAX_SAME_RETRIES,
    MAX_TOOL_ROUNDS,
    STREAM_IDLE_TIMEOUT_SEC,
)
from app.run.memory import (
    AgentRecord,
    FileFact,
    RunMemory,
    ToolEvent,
    file_fact,
    record_tool,
    reused_file_result,
    visible_text,
)
from app.run.orchestrate import (
    match_agent,
    orchestrator_instructions,
    parse_orchestrator_action,
    reject_reason,
)
from app.run import window as run_window
from app.run.mcp_bridge import get_mcp, map_openai_tool_name
from app.run.models import ActivityDag, ActivityTokens, ChatMessage, NodeLlmInfo, NodeRuntime, NodeTokens
from app.run.sse import publish
from app.runtime.errors import RuntimeApiError
from app.runtime.completions import estimate_token_count
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import CompletionRequest, CompletionResult

_REPAIR_NOTE = (
    "The last decision was not one valid JSON object. It was not shown to the user and no agent was called. "
    "Reply with one JSON object only. The task must be a short instruction. Do not paste an agent result."
)
_TOOL_DECIDE_NOTE = "Reply with one JSON object. Do not call a tool."
_SAME_RETRY = frozenset({"runtime.timeout", "runtime.unreachable", "runtime.upstream"})
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
            _clear_human_wait(ctrl, compiled)
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


def _tool_schemas(
    kinds: list[str], mcp_pairs: list[tuple[str, list[str] | None]]
) -> list[dict]:
    tools = openai_tools_for_kinds(kinds)
    bridge = get_mcp()
    if bridge and mcp_pairs:
        from app.db.settings import get_mcp_server
        from app.mcp.models import McpToolInfo
        from app.run.mcp_bridge import mcp_openai_tools

        for server_id, allow in mcp_pairs:
            row = get_mcp_server(server_id) or {}
            cached = row.get("cached_tools") or []
            infos = [
                McpToolInfo(
                    name=str(item.get("name")),
                    description=item.get("description"),
                    input_schema=item.get("input_schema") or {},
                )
                for item in cached
                if isinstance(item, dict) and item.get("name")
            ]
            if allow:
                infos = [info for info in infos if info.name in allow]
            tools.extend(mcp_openai_tools(server_id, infos))
    return tools


def _function_names(schemas: list[dict]) -> list[str]:
    names: list[str] = []
    for item in schemas:
        function = item.get("function") or {}
        name = function.get("name")
        if name:
            names.append(str(name))
    return names


def _dispatch_tool(
    ctrl: RunController,
    compiled: CompiledGraph,
    *,
    owner_id: str,
    call_name: str,
    call_arguments: str,
    tool_kinds: list[str],
    mcp,
    record: AgentRecord | None,
    reuse: bool,
) -> tuple[str, FileFact | None, bool]:
    tool_node_id = owner_id
    args = _parse_args(call_arguments)
    mapped = map_openai_tool_name(call_name)
    reused = None
    if reuse and record is not None and call_name == "file_access":
        reused = reused_file_result(
            record, str(args.get("action") or ""), str(args.get("path") or "")
        )
    if reused is not None:
        tool_result = reused
    elif mapped and mcp:
        out = mcp.call(mapped[0], mapped[1], args)
        tool_result = out.get("result") if out.get("ok") else out
    elif call_name in tool_kinds:
        tool_result: object = {"ok": False, "error": "unknown tool"}
        for edge in compiled.doc.edges:
            if edge.target != owner_id or edge.target_handle != "tool":
                continue
            tool_node = compiled.by_id.get(edge.source)
            if tool_node and str(tool_node.data.get("kind")) == call_name:
                tool_node_id = tool_node.id
                if tool_node.type == "tool":
                    _set_node(ctrl, tool_node_id, "running", wait="tool", message=call_name)
                try:
                    cid = tool_node.data.get("credentialId")
                    cred = vault_get(str(cid)) if cid else None
                    out = tools_execute.execute_first_party(
                        call_name,
                        config=tool_node.data,
                        args=args,
                        secret=cred,
                    )
                    tool_result = out.model_dump(by_alias=True)
                finally:
                    if tool_node.type == "tool":
                        _set_node(ctrl, tool_node_id, "idle")
                break
    else:
        tool_result = {"ok": False, "error": f"unknown tool {call_name}"}
    ok_tool = not (isinstance(tool_result, dict) and tool_result.get("ok") is False)
    emit_log(
        "info" if ok_tool else "warn",
        "run.tool.call",
        node_id=tool_node_id,
        payload={"name": call_name, "waitReason": "tool", "ok": ok_tool},
    )
    fact = None if reused is not None else file_fact(call_name, args, tool_result, ok=ok_tool)
    masked = str(mask_obj(tool_result))
    if record is not None:
        record_tool(
            record,
            ToolEvent(
                name=call_name,
                arguments=call_arguments or "",
                ok=ok_tool,
                result=masked[:8000],
            ),
            fact,
        )
    return masked, fact, ok_tool


def _agent_turn(
    ctrl: RunController,
    compiled: CompiledGraph,
    agent_id: str,
    user_text: str,
    conversation: list[LlmMessage],
    *,
    publish_chat: bool = True,
    memory: RunMemory | None = None,
    record: AgentRecord | None = None,
    reuse: bool = False,
) -> str | None:
    agent = compiled.agents[agent_id]
    _set_node(ctrl, agent_id, "running", wait="llm", message=user_text)
    emit_log("info", "run.agent.start", node_id=agent_id)
    snippets: list[str] = []
    for kid in agent.knowledge_node_ids:
        kn = compiled.by_id.get(kid)
        if kn is not None and kn.type == "knowledge":
            _set_node(ctrl, kid, "running", wait="knowledge")
        try:
            node = kn
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
        finally:
            if kn is not None and kn.type == "knowledge":
                _set_node(ctrl, kid, "idle")
    if agent.knowledge_node_ids:
        emit_log(
            "debug",
            "run.knowledge",
            node_id=agent_id,
            payload={"count": len(snippets)},
        )
    context = "\n".join(snippets) if snippets else "No document context."
    system = (agent.system_prompt + "\n\n# Document context\n" + context).strip()
    tools = _tool_schemas(agent.tool_kinds, agent.mcp)
    mcp = get_mcp()
    secret = None
    if agent.llm.provider != "ollama" and agent.llm.credential_id:
        secret = vault_get(agent.llm.credential_id)
    messages = [LlmMessage(role="system", content=system), *conversation]
    from app.runtime import completions as runtime_completions

    rounds = 0
    content = ""
    llm_node_id = agent.llm.node_id or agent_id
    while rounds <= MAX_TOOL_ROUNDS:
        choice = _bind_window(agent.llm, messages, memory) if memory is not None else None
        if choice is not None and not choice.fits:
            if record is not None:
                record.error = "prompt does not fit"
            _set_node(ctrl, agent_id, "done")
            emit_log("warn", "run.agent.window", node_id=agent_id)
            return ""
        options = {"num_ctx": choice.num_ctx} if choice is not None and choice.num_ctx else None
        context_max = choice.context_max if choice is not None else _static_context_max(agent.llm.num_ctx)
        context_est = run_window.prompt_tokens(messages)
        started = time.perf_counter()
        emit_log(
            "info",
            "run.llm.start",
            node_id=llm_node_id,
            payload={
                "provider": agent.llm.provider,
                "model": agent.llm.model,
                "waitReason": "llm",
                "contextMax": context_max,
            },
        )
        _set_llm(ctrl, compiled, llm_node_id, busy=True)
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
                    ollama_options=options,
                ),
                should_abort=ctrl.stop_event.is_set,
                on_progress=lambda out, rate, cap=context_max, used=context_est: (
                    _note_tokens(record, out),
                    _publish_tokens(
                        ctrl,
                        agent_id,
                        llm_node_id,
                        tokens_in=None,
                        tokens_out=out,
                        per_second=rate,
                        committed=False,
                        context_used=used,
                        context_max=cap,
                    ),
                ),
            )
            ok = True
        except Exception as exc:
            _set_llm(ctrl, compiled, llm_node_id, busy=False)
            if isinstance(exc, RuntimeApiError) and (
                exc.error_key == "run.cancelled" or ctrl.stop_event.is_set()
            ):
                return None
            if memory is not None and record is not None:
                key = exc.error_key if isinstance(exc, RuntimeApiError) else "runtime.upstream"
                record.error = key
                emit_log("warn", key, node_id=agent_id)
                insert_call(
                    run_id=ctrl.run_id or "",
                    provider=agent.llm.provider,
                    model=agent.llm.model,
                    ok=False,
                    node_id=agent_id,
                    node_name=node_label(compiled, agent_id),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    error_message=key,
                )
                _set_node(ctrl, agent_id, "done")
                return ""
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
        _set_llm(ctrl, compiled, llm_node_id, busy=False)
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
        used_now = in_final if in_final is not None else context_est
        _note_tokens(record, out_final)
        _publish_tokens(
            ctrl,
            agent_id,
            llm_node_id,
            tokens_in=in_final,
            tokens_out=out_final,
            per_second=rate_final,
            committed=True,
            context_used=used_now,
            context_max=context_max,
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
                body, _fact, _ok = _dispatch_tool(
                    ctrl,
                    compiled,
                    owner_id=agent_id,
                    call_name=call.name,
                    call_arguments=call.arguments or "",
                    tool_kinds=agent.tool_kinds,
                    mcp=mcp,
                    record=record,
                    reuse=reuse,
                )
                messages.append(
                    LlmMessage(role="tool", content=body, tool_call_id=call.id)
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


def _note_tokens(record: AgentRecord | None, out: int | None) -> None:
    if record is not None and out:
        record.saw_tokens = True


def _static_context_max(num_ctx: int | None) -> int | None:
    if isinstance(num_ctx, int) and num_ctx > 0:
        return num_ctx
    return None


def _bind_window(llm, messages: list[LlmMessage], memory: RunMemory):
    preferred = llm.num_ctx if isinstance(llm.num_ctx, int) and llm.num_ctx > 0 else None
    tag = llm.model or ""
    loaded = None
    arch = None
    if llm.provider == "ollama" and tag:
        if tag not in memory.arch:
            memory.arch[tag] = run_window.architecture_context(tag, base_url=llm.base_url)
        if tag not in memory.loaded:
            memory.loaded[tag] = run_window.loaded_context(tag, base_url=llm.base_url)
        arch = memory.arch[tag]
        loaded = memory.loaded[tag]
    need = run_window.prompt_need(messages, llm.max_tokens)
    choice = run_window.choose_window(
        need=need,
        preferred=preferred,
        loaded=loaded,
        raised=memory.raised.get(tag),
        architecture_max=arch,
        provider=llm.provider,
    )
    if choice.num_ctx and tag:
        memory.raised[tag] = choice.num_ctx
        memory.loaded[tag] = choice.num_ctx
    memory.note_window(tag, context_max=choice.context_max, need=need)
    return choice


def _publish_tokens(
    ctrl: RunController,
    agent_id: str,
    llm_node_id: str,
    *,
    tokens_in: int | None,
    tokens_out: int | None,
    per_second: float | None,
    committed: bool,
    context_used: int | None = None,
    context_max: int | None = None,
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
        context_used=context_used,
        context_max=context_max,
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
    message: str | None = None,
    llm: NodeLlmInfo | None = None,
    clear_llm: bool = False,
) -> None:
    if not ctrl.snapshot:
        return
    runtime = dict(ctrl.snapshot.nodes_runtime)
    current = runtime.get(node_id, NodeRuntime())
    update: dict[str, object] = {"status": status, "wait_reason": wait, "error": error}
    if message is not None:
        cleaned = " ".join(message.split())
        update["last_message"] = cleaned[:240] or None
    if llm is not None:
        update["llm"] = llm
    if clear_llm:
        update["llm"] = None
    runtime[node_id] = current.model_copy(update=update)
    ctrl.snapshot = ctrl.snapshot.model_copy(update={"nodes_runtime": runtime})
    _refresh_activity(ctrl)
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


def _refresh_activity(ctrl: RunController) -> None:
    snap = ctrl.snapshot
    if snap is None:
        return
    current = [
        nid for nid, rt in snap.nodes_runtime.items() if rt.status in {"running", "waiting"}
    ]
    dag = snap.activity.dag
    compiled = ctrl.compiled
    if compiled is not None:
        ids = list(compiled.agents)
        done = sum(
            1
            for aid in ids
            if snap.nodes_runtime.get(aid) is not None and snap.nodes_runtime[aid].status == "done"
        )
        pending = [
            aid
            for aid in ids
            if snap.nodes_runtime.get(aid) is None or snap.nodes_runtime[aid].status == "idle"
        ]
        dag = ActivityDag(completed=done, total=len(ids), pending_node_ids=pending)
    ctrl.snapshot = snap.model_copy(
        update={
            "activity": snap.activity.model_copy(update={"current_node_ids": current, "dag": dag})
        }
    )


def _set_llm(ctrl: RunController, compiled: CompiledGraph, llm_node_id: str, *, busy: bool) -> None:
    if not llm_node_id:
        return
    node = compiled.by_id.get(llm_node_id)
    if node is None or node.type != "llm":
        return
    if busy:
        info = NodeLlmInfo(
            model=str(node.data.get("model") or ""),
            provider=str(node.data.get("provider") or "ollama"),
            node_id=llm_node_id,
        )
        _set_node(ctrl, llm_node_id, "running", wait="llm", llm=info)
    else:
        _set_node(ctrl, llm_node_id, "idle", clear_llm=True)


def _run_orchestrator(ctrl: RunController, compiled: CompiledGraph, user_text: str) -> str:
    orch = compiled.orchestrator
    if orch is None:
        return "failed"
    memory = RunMemory()
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
    tool_schemas = _tool_schemas(orch.tool_kinds, orch.mcp)
    names = [(agent_id, name) for agent_id, name, _ in roster]
    steps = 0
    while not ctrl.stop_event.is_set():
        steps += 1
        if steps > MAX_ORCHESTRATOR_STEPS:
            emit_log("error", "run.stepLimit", node_id=orch.node_id)
            _store_memory(ctrl, memory)
            return "failed"
        offered = tool_schemas if memory.allow_own_tools else []
        system = orchestrator_instructions(orch.system_prompt, roster, _function_names(offered))
        action = _orchestrator_action(ctrl, compiled, system, memory, offered)
        memory.clear_anomaly()
        _store_memory(ctrl, memory)
        if action is None:
            return "cancelled" if ctrl.stop_event.is_set() else "failed"
        if action.get("action") == "failed-window":
            _set_node(ctrl, orch.node_id, "error", error="run.orchestrator.window")
            return "failed"
        if action.get("action") == "unreadable":
            ctrl.fail_message = "run.orchestrator.unreadable"
            ctrl.fail_class = "orchestrator"
            ctrl.last_error_node_id = orch.node_id
            emit_log("error", "run.orchestrator.unreadable", node_id=orch.node_id)
            _set_node(ctrl, orch.node_id, "error", error="run.orchestrator.unreadable")
            return "failed"
        kind = action.get("action") or "reply"
        text = action.get("text") or ""
        if kind == "ask":
            _speak(ctrl, compiled, memory, "ask", text or "…", wait=True)
            reply = _queue_get(ctrl)
            if not reply or ctrl.stop_event.is_set():
                return "cancelled"
            memory.add_user(reply)
            _clear_human_wait(ctrl, compiled)
            continue
        if kind == "call":
            if _orchestrator_call(ctrl, compiled, memory, names, action, user_text) == "cancelled":
                return "cancelled"
            continue
        if kind == "finish":
            if text.strip():
                _publish_assistant(ctrl, text.strip())
                memory.add_spoken("finish", text.strip())
            _finish_targets(ctrl, compiled, orch, text)
            _store_memory(ctrl, memory)
            return "succeeded"
        if text.strip():
            _publish_assistant(ctrl, text.strip())
            memory.add_spoken("reply", text.strip())
        continue
    _store_memory(ctrl, memory)
    return "cancelled"


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
    task = (action.get("task") or "").strip() or memory.last_user() or user_text
    if agent_id is None or agent_id not in compiled.agents:
        memory.add_note(f"Unknown agent: {token}. Use an id from the roster.")
        return "continue"
    agent = compiled.agents[agent_id]
    has_tools = bool(agent.tool_kinds or agent.mcp)
    source = memory.resolve_source(action.get("source") or "", names)
    if source.ambiguous:
        memory.add_note("Source is ambiguous. Set source to one id: " + ", ".join(source.ambiguous))
        return "continue"
    if source.missing:
        memory.add_note(f"Unknown source: {source.missing}.")
        return "continue"
    if source.auto:
        emit_log("info", "run.memory.source", node_id=agent_id)
    name = dict(names).get(agent_id, agent_id)
    record = memory.begin_call(agent_id, name, task, has_tools)
    memory.allow_own_tools = True
    orch = compiled.orchestrator
    if orch is not None:
        _set_node(ctrl, orch.node_id, "waiting")
    delivered = memory.agent_message(agent_id, task, has_tools, source.text)
    attempt = 0
    continued = False
    while not ctrl.stop_event.is_set():
        text = _agent_turn(
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
            return "cancelled" if ctrl.stop_event.is_set() else "continue"
        if record.error == "prompt does not fit":
            memory.set_anomaly(record)
            return "continue"
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
            memory.set_anomaly(record)
            return "continue"
        visible = visible_text(text or "")
        if text and not visible:
            memory.reject(text, "empty")
        if not visible and not record.tool_ok:
            record.error = "empty result"
            memory.set_anomaly(record)
            return "continue"
        record.text = visible
        record.finished = True
        if any(not fact.ok for fact in record.files):
            record.error = "tool failed"
            memory.set_anomaly(record)
        else:
            _publish_progress(ctrl, name, record)
            memory.add_note(f"Status already shown to the user: {name} finished.")
        return "continue"
    return "cancelled"


def _finish_targets(ctrl: RunController, compiled: CompiledGraph, orch, text: str) -> None:
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
        _wait_chat(ctrl, compiled)


def _wait_chat(ctrl: RunController, compiled: CompiledGraph) -> None:
    orch = compiled.orchestrator
    if orch is not None:
        _set_node(ctrl, orch.node_id, "waiting", wait="human")
    if compiled.chat_input:
        _set_node(ctrl, compiled.chat_input.id, "waiting", wait="human")
    emit_log("info", "run.wait.human", node_id=orch.node_id if orch else None)


def _clear_human_wait(ctrl: RunController, compiled: CompiledGraph) -> None:
    if compiled.chat_input:
        _set_node(ctrl, compiled.chat_input.id, "idle")


def _orchestrator_action(
    ctrl: RunController,
    compiled: CompiledGraph,
    system: str,
    memory: RunMemory,
    tools: list[dict],
) -> dict[str, str] | None:
    orch = compiled.orchestrator
    if orch is None:
        return None
    repairs = 0
    model_retries = 0
    rounds = 0
    offered = list(tools)
    messages = memory.orchestrator_messages(system)
    mcp = get_mcp()
    while not ctrl.stop_event.is_set():
        choice = _bind_window(orch.llm, messages, memory)
        if not choice.fits:
            ctrl.fail_message = "run.orchestrator.window"
            ctrl.fail_class = "orchestrator"
            ctrl.last_error_node_id = orch.node_id
            emit_log("error", "run.orchestrator.window", node_id=orch.node_id)
            return {"action": "failed-window"}
        _set_node(ctrl, orch.node_id, "running", wait="llm")
        ctrl.flush_chat(generating=True)
        llm = orch.llm
        secret = None
        if llm.provider != "ollama" and llm.credential_id:
            secret = vault_get(llm.credential_id)
        started = time.perf_counter()
        llm_node_id = llm.node_id or orch.node_id
        context_max = choice.context_max
        context_est = run_window.prompt_tokens(messages)
        options = {"num_ctx": choice.num_ctx} if choice.num_ctx else None
        emit_log(
            "info",
            "run.llm.start",
            node_id=llm_node_id,
            payload={"provider": llm.provider, "model": llm.model, "waitReason": "llm", "contextMax": context_max},
        )
        from app.runtime import completions as runtime_completions

        _set_llm(ctrl, compiled, llm_node_id, busy=True)
        try:
            result = runtime_completions.complete_live(
                CompletionRequest(
                    provider=llm.provider,  # type: ignore[arg-type]
                    model=llm.model,
                    messages=messages,
                    base_url=llm.base_url,
                    credential_id=llm.credential_id,
                    secret=secret,
                    temperature=llm.temperature,
                    max_tokens=llm.max_tokens,
                    tools=offered or None,
                    timeout_sec=STREAM_IDLE_TIMEOUT_SEC,
                    ollama_options=options,
                ),
                should_abort=ctrl.stop_event.is_set,
                on_progress=lambda out, rate, cap=context_max, used=context_est: _publish_tokens(
                    ctrl,
                    orch.node_id,
                    llm_node_id,
                    tokens_in=None,
                    tokens_out=out,
                    per_second=rate,
                    committed=False,
                    context_used=used,
                    context_max=cap,
                ),
            )
        except Exception as exc:
            _set_llm(ctrl, compiled, llm_node_id, busy=False)
            if isinstance(exc, RuntimeApiError) and (
                exc.error_key == "run.cancelled" or ctrl.stop_event.is_set()
            ):
                return None
            key = exc.error_key if isinstance(exc, RuntimeApiError) else "runtime.upstream"
            if key in _SAME_RETRY and model_retries < MAX_SAME_RETRIES:
                model_retries += 1
                emit_log("warn", key, node_id=orch.node_id)
                continue
            ctrl.last_error_node_id = orch.node_id
            emit_log("error", str(exc), node_id=orch.node_id, stack=traceback.format_exc())
            _set_node(ctrl, orch.node_id, "error", error=str(exc))
            raise
        _set_llm(ctrl, compiled, llm_node_id, busy=False)
        duration_ms = int((time.perf_counter() - started) * 1000)
        usage = result.usage
        out_final = usage.completion_tokens if usage else (
            estimate_token_count(result.content) if result.content else None
        )
        in_final = usage.prompt_tokens if usage else context_est
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
            context_used=in_final,
            context_max=context_max,
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
        if result.tool_calls and rounds < MAX_ORCHESTRATOR_TOOL_ROUNDS and offered:
            rounds += 1
            model_retries = 0
            memory.allow_own_tools = False
            _set_node(ctrl, orch.node_id, "running", wait="tool")
            messages.append(
                LlmMessage(
                    role="assistant",
                    content=result.content,
                    tool_calls=result.tool_calls,
                )
            )
            for call in result.tool_calls:
                body, fact, ok_tool = _dispatch_tool(
                    ctrl,
                    compiled,
                    owner_id=orch.node_id,
                    call_name=call.name,
                    call_arguments=call.arguments or "",
                    tool_kinds=orch.tool_kinds,
                    mcp=mcp,
                    record=None,
                    reuse=False,
                )
                memory.note_own_tool(
                    ToolEvent(
                        name=call.name,
                        arguments=call.arguments or "",
                        ok=ok_tool,
                        result=body[:8000],
                    ),
                    fact,
                )
                messages.append(LlmMessage(role="tool", content=body, tool_call_id=call.id))
            if rounds >= MAX_ORCHESTRATOR_TOOL_ROUNDS:
                offered = []
                messages.append(LlmMessage(role="user", content=_TOOL_DECIDE_NOTE))
            continue
        if result.tool_calls:
            offered = []
            memory.allow_own_tools = False
            raw = result.content or ""
            if not raw.strip():
                repairs += 1
                emit_log("info", "run.orchestrator.repair", node_id=orch.node_id)
                if repairs <= MAX_CONTROL_REPAIRS:
                    memory.add_note(_TOOL_DECIDE_NOTE)
                    messages.append(LlmMessage(role="user", content=_TOOL_DECIDE_NOTE))
                    continue
                return {"action": "unreadable"}
        raw = result.content or ""
        reason = reject_reason(raw)
        if reason:
            memory.reject(raw, reason)
            repairs += 1
            emit_log("info", "run.orchestrator.repair", node_id=orch.node_id)
            if repairs <= MAX_CONTROL_REPAIRS:
                memory.add_note(_REPAIR_NOTE)
                messages.append(LlmMessage(role="user", content=_REPAIR_NOTE))
                continue
            return {"action": "unreadable"}
        return parse_orchestrator_action(raw)
    return None


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
