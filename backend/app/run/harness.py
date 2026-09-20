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
from app.run.limits import DEFAULT_SCORE_MIN, DEFAULT_TOP_K, MAX_AGENT_INVOCATIONS, MAX_TOOL_ROUNDS
from app.run.mcp_bridge import get_mcp, map_openai_tool_name
from app.run.models import ChatMessage, NodeRuntime
from app.run.sse import publish
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import CompletionRequest, CompletionResult
from app.tools.catalog import openai_tools_for_kinds
from app.tools import execute as tools_execute


def run_harness(ctrl: RunController, compiled: CompiledGraph) -> None:
    outcome = "failed"
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
                    outcome = "failed"
                    return
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
                outcome = "failed"
                return
            text = _agent_turn(ctrl, compiled, node_id, payload, conversation)
            if text is None:
                if ctrl.stop_event.is_set():
                    break
                continue
            for target in compiled.agents[node_id].outbound_message:
                pending.append((target, text))
        if ctrl.stop_event.is_set():
            outcome = "cancelled"
        elif end_hit:
            outcome = "succeeded"
        else:
            outcome = "failed"
    except Exception as exc:
        emit_log("error", str(exc), stack=traceback.format_exc())
        outcome = "failed"
    finally:
        if outcome == "succeeded":
            emit_log("info", "run.succeeded")
        elif outcome == "cancelled":
            emit_log("warn", "run.cancelled")
        else:
            emit_log("error", "run.failed")
        ctrl.finish(outcome)


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


def _agent_turn(
    ctrl: RunController,
    compiled: CompiledGraph,
    agent_id: str,
    user_text: str,
    conversation: list[LlmMessage],
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
            result: CompletionResult = runtime_completions.complete(
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
                    timeout_sec=120,
                )
            )
            ok = True
        except Exception as exc:
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
        insert_call(
            run_id=ctrl.run_id or "",
            provider=agent.llm.provider,
            model=agent.llm.model,
            ok=ok,
            node_id=agent_id,
            node_name=node_label(compiled, agent_id),
            duration_ms=duration_ms,
            tokens_in=usage.prompt_tokens if usage else None,
            tokens_out=usage.completion_tokens if usage else None,
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
    if compiled.chat_input and content:
        msg = ChatMessage(
            id=str(uuid.uuid4()),
            run_id=ctrl.run_id or "",
            role="assistant",
            content=content,
            created_at=utc_now(),
        )
        ctrl.conversation.append(msg)
        publish("chat", {"runId": ctrl.run_id, "message": msg.model_dump(by_alias=True)})
        conversation.append(LlmMessage(role="assistant", content=content))
    return content


def _parse_args(raw: str) -> dict:
    import json

    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


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


def _publish_user(ctrl: RunController, text: str) -> None:
    msg = ChatMessage(
        id=str(uuid.uuid4()),
        run_id=ctrl.run_id or "",
        role="user",
        content=text,
        created_at=utc_now(),
    )
    ctrl.conversation.append(msg)
    publish("chat", {"runId": ctrl.run_id, "message": msg.model_dump(by_alias=True)})
