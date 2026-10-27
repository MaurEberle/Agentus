"""One agent invocation. The caller supplies the envelope."""

from __future__ import annotations

import time
import traceback
import uuid

from app.db.engine import utc_now
from app.db.runs import insert_call
from app.db.vault import get as vault_get
from app.run import turn_runtime
from app.run import window as run_window
from app.run.compile import CompiledGraph
from app.run.controller import RunController, emit_log, node_label
from app.run.knowledge import retrieve
from app.run.limits import (
    DEFAULT_SCORE_MIN,
    DEFAULT_TOP_K,
    MAX_AGENT_THINKS,
    MAX_CLOSING_THINK_TOKENS,
    MAX_EMPTY_STOPS,
    MAX_FAILED_TOOL_CALLS,
    MAX_SHORT_THINKS,
    MAX_TOOL_JSON_ATTEMPTS,
    STREAM_IDLE_TIMEOUT_SEC,
    SUBSTANTIAL_RESULT_CHARS,
)
from app.run.memory import (
    AgentRecord,
    RunMemory,
    ToolEvent,
    file_fact,
    record_tool,
    visible_text,
)
from app.run.models import ChatMessage
from app.run.orchestrate import agent_think_text
from app.run.turn_runtime import _FILE_MUTATIONS, _FILE_PREP_ACTIONS
from app.runtime.completions import estimate_token_count
from app.runtime.errors import RuntimeApiError, truncated_tool_call_name
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import CompletionRequest, CompletionResult

_AGENT_THINK = (
    "You may think first with {\"action\":\"think\",\"text\":\"...\"} or a think block. "
    "Think is not the result and is not shown to the user. After think, write the visible result."
)

_AGENT_THINK_TOOLS = (
    "You may think first with a think block. "
    "Think is not the result and is not shown to the user. After think, call a tool with a tool call. "
    "Do not write a JSON object for think when you have tools."
)

_TOOL_USE_NOTE = (
    "You have tools. Call a tool with a tool call. A final sentence without a tool call is discarded."
)

_TOOL_REQUIRED = (
    "You must call a tool with a tool call. You may think first. "
    "A final sentence without a tool call is discarded."
)

_TOOL_ANSWER = (
    "You already have tool results. Answer the user from those results. "
    "Call a tool only if you still need data you do not have."
)

_TOOL_DONE = (
    "The file work succeeded. Write a short visible result for the next node. "
    "Do not think again."
)

_EMPTY_STOP_NOTE = (
    "The last reply was empty and was discarded. The task is not finished. "
    "Call a tool with a tool call and continue the remaining work."
)

_TOOL_JSON_NOTE = (
    "The last tool call to {name} was discarded: its JSON arguments were truncated. "
    "Call the tool again with complete JSON. Prefer a smaller write if the file is large."
)


def _agent_tool_failures_stop(
    ctrl: RunController,
    agent_id: str,
    record: AgentRecord | None,
    failed_tools: int,
) -> bool:
    """True: orchestrator anomaly (break). False: abort the linear turn."""
    emit_log(
        "warn",
        "run.agent.toolFailures",
        node_id=agent_id,
        payload={"failed": failed_tools},
    )
    if record is not None:
        record.error = "too many tool failures"
        return True
    turn_runtime._set_node(ctrl, agent_id, "error", error="run.agent.toolFailures")
    ctrl.fail_message = "run.agent.toolFailures"
    ctrl.fail_class = "unknown"
    ctrl.last_error_node_id = agent_id
    return False

def _agent_empty_stops_stop(
    ctrl: RunController,
    agent_id: str,
    record: AgentRecord | None,
    stops: int,
) -> bool:
    """True: orchestrator anomaly (break). False: fail the linear run."""
    emit_log(
        "warn",
        "run.agent.emptyStops",
        node_id=agent_id,
        payload={"stops": stops},
    )
    if record is not None:
        record.error = "empty stops"
        return True
    turn_runtime._set_node(ctrl, agent_id, "error", error="run.agent.emptyStops")
    ctrl.fail_message = "run.agent.emptyStops"
    ctrl.fail_class = "unknown"
    ctrl.last_error_node_id = agent_id
    return False

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
    turn_runtime._set_node(ctrl, agent_id, "running", wait="llm", message=user_text)
    emit_log("info", "run.agent.start", node_id=agent_id)
    snippets: list[str] = []
    for kid in agent.knowledge_node_ids:
        kn = compiled.by_id.get(kid)
        if kn is not None and kn.type == "knowledge":
            turn_runtime._set_node(ctrl, kid, "running", wait="knowledge")
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
                turn_runtime._set_node(ctrl, kid, "idle")
    if agent.knowledge_node_ids:
        emit_log(
            "debug",
            "run.knowledge",
            node_id=agent_id,
            payload={"count": len(snippets)},
        )
    context = "\n".join(snippets) if snippets else "No document context."
    system = (agent.system_prompt + "\n\n# Document context\n" + context).strip()
    tools = turn_runtime._tool_schemas(
        agent.tool_kinds,
        agent.mcp,
        agent.file_actions,
        terminal_programs=agent.terminal_programs,
        terminal_unrestricted=agent.terminal_unrestricted,
    )
    system = system + "\n\n" + (_AGENT_THINK_TOOLS if tools else _AGENT_THINK)
    if tools:
        system = system + "\n\n" + _TOOL_REQUIRED
    mcp = turn_runtime.get_mcp()
    secret = None
    if agent.llm.provider != "ollama" and agent.llm.credential_id:
        secret = vault_get(agent.llm.credential_id)
    messages = [LlmMessage(role="system", content=system), *conversation]
    from app.runtime import completions as runtime_completions

    failed_tools = 0
    json_attempts = 0
    nudges = 0
    thinks = 0
    short_thinks = 0
    empty_stops = 0
    content = ""
    best_visible = ""
    offered = tools
    tool_ok = bool(record is not None and record.tool_ok)
    wrote_ok = False
    file_prep = False
    wrote_paths: list[str] = []
    if record is not None:
        for fact in record.files:
            if not fact.ok:
                continue
            if fact.action in _FILE_MUTATIONS:
                wrote_ok = True
                if fact.path:
                    wrote_paths.append(fact.path)
            elif fact.action in _FILE_PREP_ACTIONS:
                file_prep = True
    llm_node_id = agent.llm.node_id or agent_id
    try:
        while not ctrl.stop_event.is_set():
            window_mem = memory if memory is not None else RunMemory()
            choice = turn_runtime._bind_window(agent.llm, messages, window_mem)
            if not choice.fits:
                if record is not None:
                    record.error = "prompt does not fit"
                turn_runtime._set_node(ctrl, agent_id, "done")
                emit_log("warn", "run.agent.window", node_id=agent_id)
                return ""
            options = turn_runtime._ollama_options(agent.llm, choice)
            context_max = choice.context_max if choice.context_max is not None else turn_runtime._static_context_max(agent.llm.num_ctx)
            context_est = run_window.prompt_tokens(messages)
            turn_runtime._prepare_resident(compiled, agent.llm)
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
            turn_runtime._set_llm(ctrl, compiled, llm_node_id, busy=True)
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
                        tools=offered or None,
                        timeout_sec=STREAM_IDLE_TIMEOUT_SEC,
                        ollama_options=options,
                    ),
                    should_abort=ctrl.stop_event.is_set,
                    on_progress=lambda out, rate, cap=context_max, used=context_est: (
                        _note_tokens(record, out),
                        turn_runtime._publish_tokens(
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
                json_attempts = 0
            except Exception as exc:
                if isinstance(exc, RuntimeApiError) and (
                    exc.error_key == "run.cancelled" or ctrl.stop_event.is_set()
                ):
                    return None
                tool_name = truncated_tool_call_name(exc)
                if tool_name is not None:
                    json_attempts += 1
                    insert_call(
                        run_id=ctrl.run_id or "",
                        provider=agent.llm.provider,
                        model=agent.llm.model,
                        ok=False,
                        node_id=agent_id,
                        node_name=node_label(compiled, agent_id),
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        error_message="runtime.badRequest",
                    )
                    emit_log(
                        "warn",
                        "run.agent.toolJson",
                        node_id=agent_id,
                        payload={
                            "name": tool_name,
                            "attempt": json_attempts,
                            "max": MAX_TOOL_JSON_ATTEMPTS,
                            **(turn_runtime._runtime_error_payload(exc) or {}),
                        },
                    )
                    messages.append(
                        LlmMessage(
                            role="user",
                            content=_TOOL_JSON_NOTE.format(name=tool_name),
                        )
                    )
                    if json_attempts < MAX_TOOL_JSON_ATTEMPTS:
                        continue
                    json_attempts = 0
                    failed_tools += 1
                    if record is not None:
                        record_tool(
                            record,
                            ToolEvent(
                                name=tool_name,
                                arguments="",
                                ok=False,
                                result="truncated tool JSON",
                            ),
                            file_fact(
                                tool_name,
                                {},
                                {"ok": False, "error": "truncated tool JSON"},
                                ok=False,
                            ),
                        )
                    if failed_tools >= MAX_FAILED_TOOL_CALLS:
                        if _agent_tool_failures_stop(ctrl, agent_id, record, failed_tools):
                            content = ""
                            break
                        return None
                    continue
                if memory is not None and record is not None:
                    key = exc.error_key if isinstance(exc, RuntimeApiError) else "runtime.upstream"
                    record.error = key
                    emit_log("warn", key, node_id=agent_id, payload=turn_runtime._runtime_error_payload(exc))
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
                    turn_runtime._set_node(ctrl, agent_id, "done")
                    return ""
                ctrl.last_error_node_id = agent_id
                emit_log(
                    "error",
                    str(exc),
                    node_id=agent_id,
                    payload=turn_runtime._runtime_error_payload(exc),
                    stack=traceback.format_exc(),
                )
                turn_runtime._set_node(ctrl, agent_id, "error", error=str(exc))
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
            used_now = in_final if in_final is not None else context_est
            _note_tokens(record, out_final)
            turn_runtime._publish_tokens(
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
                payload=turn_runtime._completion_log_payload(
                    result,
                    {
                        "model": agent.llm.model,
                        "durationMs": duration_ms,
                        "tokensIn": usage.prompt_tokens if usage else None,
                        "tokensOut": usage.completion_tokens if usage else None,
                    },
                ),
            )
            turn_runtime._log_vram_compare(agent.llm, options, choice, llm_node_id)
            result = turn_runtime._with_salvaged_tools(result, offered)
            if result.tool_calls:
                thinks = 0
                short_thinks = 0
                empty_stops = 0
                turn_runtime._set_node(ctrl, agent_id, "running", wait="tool")
                messages.append(
                    LlmMessage(
                        role="assistant",
                        content=result.content,
                        tool_calls=result.tool_calls,
                    )
                )
                hit_failure_limit = False
                for call in result.tool_calls:
                    body, _fact, ok_call = turn_runtime._dispatch_tool(
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
                    if ok_call:
                        failed_tools = 0
                        tool_ok = True
                        if _fact is not None and _fact.action in _FILE_MUTATIONS:
                            wrote_ok = True
                            if _fact.path:
                                wrote_paths.append(_fact.path)
                        elif _fact is not None and _fact.action in _FILE_PREP_ACTIONS:
                            file_prep = True
                    else:
                        failed_tools += 1
                    messages.append(
                        LlmMessage(
                            role="tool",
                            content=body,
                            tool_call_id=call.id or None,
                            name=call.name or None,
                        )
                    )
                    if failed_tools >= MAX_FAILED_TOOL_CALLS:
                        if _agent_tool_failures_stop(ctrl, agent_id, record, failed_tools):
                            content = result.content or ""
                            hit_failure_limit = True
                            break
                        return None
                if hit_failure_limit:
                    break
                if wrote_ok:
                    _set_system_note(messages, _TOOL_REQUIRED, _TOOL_DONE)
                    _set_system_note(messages, _TOOL_ANSWER, _TOOL_DONE)
                elif tool_ok and not file_prep:
                    _set_system_note(messages, _TOOL_REQUIRED, _TOOL_ANSWER)
                continue
            truncated = turn_runtime._result_truncated(result)
            think_body = agent_think_text(
                result.content or "",
                result.reasoning or "",
                has_tools=bool(offered),
            )
            if truncated and think_body is None and not result.tool_calls:
                think_body = (result.content or "").strip() or (result.reasoning or "").strip() or "…"
            if truncated and not result.tool_calls:
                emit_log(
                    "warn",
                    "run.agent.truncated",
                    node_id=agent_id,
                    payload=turn_runtime._completion_log_payload(result),
                )
            if think_body is not None:
                tokens = _think_out_tokens(result, out_final)
                result_body = "" if truncated else think_body
                if wrote_ok and tokens <= MAX_CLOSING_THINK_TOKENS:
                    content = _think_as_result(result_body, wrote_paths, content)
                    break
                thinks += 1
                if tokens <= 1:
                    short_thinks += 1
                else:
                    short_thinks = 0
                    empty_stops = 0
                emit_log(
                    "info",
                    "run.agent.think",
                    node_id=agent_id,
                    payload={"text": think_body},
                )
                turn_runtime._set_node(ctrl, agent_id, "running", wait="thinking")
                looped = short_thinks >= MAX_SHORT_THINKS
                if looped or thinks >= MAX_AGENT_THINKS:
                    if wrote_ok:
                        content = _think_as_result(result_body, wrote_paths, content)
                        break
                    log_key = "run.agent.thinkLoop" if looped else "run.agent.thinkLimit"
                    emit_log(
                        "warn",
                        log_key,
                        node_id=agent_id,
                        payload={"thinks": short_thinks if looped else thinks},
                    )
                    if record is not None:
                        record.error = "think loop" if looped else "too many thinks"
                        content = ""
                        break
                    turn_runtime._set_node(ctrl, agent_id, "error", error=log_key)
                    ctrl.fail_message = log_key
                    ctrl.fail_class = "unknown"
                    ctrl.last_error_node_id = agent_id
                    return None
                stored = (
                    (result.content or "").strip()
                    or (result.reasoning or "").strip()
                    or '{"action":"think"}'
                )
                _store_think(messages, stored)
                continue
            content = result.content or ""
            visible = visible_text(content)
            if len(visible) > len(best_visible):
                best_visible = visible
            need_tool = (not tool_ok) or (
                file_prep
                and not wrote_ok
                and len(visible) < SUBSTANTIAL_RESULT_CHARS
            )
            if (
                offered
                and not result.tool_calls
                and need_tool
                and nudges < 1
            ):
                nudges += 1
                messages.append(LlmMessage(role="assistant", content=content))
                messages.append(LlmMessage(role="user", content=_TOOL_USE_NOTE))
                continue
            if wrote_ok and not (content or "").strip():
                empty_stops += 1
                if empty_stops < MAX_EMPTY_STOPS:
                    emit_log(
                        "warn",
                        "run.agent.emptyStop",
                        node_id=agent_id,
                        payload={"attempt": empty_stops, "max": MAX_EMPTY_STOPS},
                    )
                    _set_system_note(messages, _TOOL_DONE, _TOOL_REQUIRED)
                    messages.append(LlmMessage(role="user", content=_EMPTY_STOP_NOTE))
                    turn_runtime._set_node(ctrl, agent_id, "running", wait="llm")
                    continue
                if _agent_empty_stops_stop(ctrl, agent_id, record, empty_stops):
                    content = ""
                    break
                return None
            if not wrote_ok and len(visible_text(content or "")) < len(best_visible):
                content = best_visible
            break
        turn_runtime._set_node(ctrl, agent_id, "done")
        emit_log("info", "run.agent.done", node_id=agent_id)
        if publish_chat and compiled.chat_input:
            text = (content or "").strip()
            if not text and record is not None:
                for event in reversed(record.tools):
                    if event.result:
                        text = event.result[:4000]
                        break
            if text:
                msg = ChatMessage(
                    id=str(uuid.uuid4()),
                    run_id=ctrl.run_id or "",
                    role="assistant",
                    content=text,
                    created_at=utc_now(),
                )
                ctrl.remember_chat(msg, generating=False)
                conversation.append(LlmMessage(role="assistant", content=text))
                content = text
        return content
    finally:
        turn_runtime._set_llm(ctrl, compiled, llm_node_id, busy=False)

def _think_out_tokens(result: CompletionResult, out_final: int | None) -> int:
    if out_final is not None:
        return out_final
    return estimate_token_count((result.content or "") + (result.reasoning or ""))

def _think_as_result(body: str, paths: list[str], fallback: str) -> str:
    text = (body or "").strip()
    if text and text != "…":
        return text
    if paths:
        return ", ".join(paths)
    return fallback or ""

def _store_think(messages: list[LlmMessage], stored: str) -> None:
    """Keep a single trailing assistant think. Gemma/Ollama reject two at the end."""
    think = LlmMessage(role="assistant", content=stored)
    if messages and messages[-1].role == "assistant" and not messages[-1].tool_calls:
        messages[-1] = think
        return
    messages.append(think)

def _set_system_note(messages: list[LlmMessage], old: str, new: str) -> None:
    if not messages or messages[0].role != "system":
        return
    text = messages[0].content or ""
    if old in text:
        messages[0] = messages[0].model_copy(update={"content": text.replace(old, new)})

def _note_tokens(record: AgentRecord | None, out: int | None) -> None:
    if record is not None and out:
        record.saw_tokens = True

