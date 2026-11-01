"""One orchestrator model call: own tools, then one control decision."""

from __future__ import annotations

import time
import traceback

from app.db.runs import insert_call
from app.db.vault import get as vault_get
from app.run import agent_turn, dispatch, turn_runtime
from app.run import window as run_window
from app.run.compile import CompiledGraph
from app.run.controller import RunController, emit_log, node_label
from app.run.limits import (
    MAX_CONTROL_REPAIRS,
    MAX_ORCHESTRATOR_FAILED_THINKS,
    MAX_ORCHESTRATOR_FAILED_TOOLS,
    MAX_SAME_RETRIES,
    STREAM_IDLE_TIMEOUT_SEC,
)
from app.run.memory import RunMemory, ToolEvent
from app.run.orchestrate import control_source, match_agent, parse_orchestrator_action, reject_reason
from app.run.turn_runtime import _SAME_RETRY
from app.runtime.completions import estimate_token_count
from app.runtime.errors import RuntimeApiError
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import CompletionRequest, CompletionResult

_REPAIR_NOTE = (
    "The last decision was not one valid JSON object. It was not shown to the user and no agent was called. "
    "Reply with one JSON object only. The task must be a short instruction. Do not paste an agent result."
)

_TOOL_DECIDE_NOTE = "Reply with one JSON object. Do not call a tool."

_TOOL_THINK_NOTE = (
    "Five tool calls failed in a row. Think, then decide with one JSON object or a working tool call. "
    "Do not repeat the same failed call."
)


def _control_raw(result: CompletionResult) -> str:
    return control_source(result.content or "", result.reasoning or "")

def _repair_payload(reason: str, raw: str) -> dict[str, str]:
    return {"reason": reason, "body": (raw or "").strip()}

def _log_repair(node_id: str, reason: str, raw: str) -> None:
    emit_log(
        "info",
        "run.orchestrator.repair",
        node_id=node_id,
        payload=_repair_payload(reason, raw),
    )

def _give_up(block_reply: bool) -> dict[str, str]:
    return {"action": "think" if block_reply else "unreadable"}


def _fail_orch_tools(ctrl: RunController, node_id: str, failed: int) -> dict[str, str]:
    emit_log(
        "error",
        "run.orchestrator.toolFailures",
        node_id=node_id,
        payload={"failed": failed},
    )
    ctrl.fail_message = "run.orchestrator.toolFailures"
    ctrl.fail_class = "orchestrator"
    ctrl.last_error_node_id = node_id
    turn_runtime._set_node(ctrl, node_id, "error", error="run.orchestrator.toolFailures")
    return {"action": "failed-tools"}

def _tag_tokens(
    action: dict[str, str], result: CompletionResult, out_final: int | None
) -> dict[str, str]:
    tagged = dict(action)
    tagged["_tokens"] = str(agent_turn._think_out_tokens(result, out_final))
    return tagged

def _pop_tokens(action: dict[str, str] | None) -> int | None:
    if not action or "_tokens" not in action:
        return None
    raw = action.pop("_tokens")
    try:
        return int(raw)
    except ValueError:
        return None

def _orchestrator_action(
    ctrl: RunController,
    compiled: CompiledGraph,
    system: str,
    memory: RunMemory,
    tools: list[dict],
    names: list[tuple[str, str]],
    *,
    block_reply: bool,
) -> dict[str, str] | None:
    orch = compiled.orchestrator
    if orch is None:
        return None
    repairs = 0
    model_retries = 0
    offered = list(tools)
    messages = memory.orchestrator_messages(system)
    mcp = turn_runtime.get_mcp()
    llm_node_id = orch.llm.node_id or orch.node_id
    action: dict[str, str] | None = None
    try:
        while not ctrl.stop_event.is_set():
            choice = turn_runtime._bind_window(orch.llm, messages, memory)
            if not choice.fits:
                ctrl.fail_message = "run.orchestrator.window"
                ctrl.fail_class = "orchestrator"
                ctrl.last_error_node_id = orch.node_id
                emit_log("error", "run.orchestrator.window", node_id=orch.node_id)
                action = {"action": "failed-window"}
                return action
            turn_runtime._set_node(ctrl, orch.node_id, "running", wait="llm")
            ctrl.flush_chat(generating=True)
            llm = orch.llm
            secret = None
            if llm.provider != "ollama" and llm.credential_id:
                secret = vault_get(llm.credential_id)
            started = time.perf_counter()
            llm_node_id = llm.node_id or orch.node_id
            context_max = choice.context_max
            context_est = run_window.prompt_tokens(messages)
            options = turn_runtime._ollama_options(llm, choice)
            turn_runtime._prepare_resident(compiled, llm)
            emit_log(
                "info",
                "run.llm.start",
                node_id=llm_node_id,
                payload={"provider": llm.provider, "model": llm.model, "waitReason": "llm", "contextMax": context_max},
            )
            from app.runtime import completions as runtime_completions

            turn_runtime._set_llm(ctrl, compiled, llm_node_id, busy=True)
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
                    on_progress=lambda out, rate, cap=context_max, used=context_est: turn_runtime._publish_tokens(
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
                emit_log(
                    "error",
                    str(exc),
                    node_id=orch.node_id,
                    payload=turn_runtime._runtime_error_payload(exc),
                    stack=traceback.format_exc(),
                )
                turn_runtime._set_node(ctrl, orch.node_id, "error", error=str(exc))
                raise
            duration_ms = int((time.perf_counter() - started) * 1000)
            usage = result.usage
            out_final = usage.completion_tokens if usage else (
                estimate_token_count(result.content) if result.content else None
            )
            in_final = usage.prompt_tokens if usage else context_est
            rate_final = None
            if out_final is not None and duration_ms > 0:
                rate_final = out_final / max(duration_ms / 1000.0, 0.05)
            turn_runtime._publish_tokens(
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
            emit_log(
                "debug",
                "run.llm.done",
                node_id=llm_node_id,
                payload=turn_runtime._completion_log_payload(
                    result,
                    {
                        "model": llm.model,
                        "durationMs": duration_ms,
                        "tokensIn": in_final,
                        "tokensOut": out_final,
                    },
                ),
            )
            turn_runtime._log_vram_compare(llm, options, choice, llm_node_id)
            result = turn_runtime._with_salvaged_tools(result, offered)
            if result.tool_calls and offered:
                model_retries = 0
                memory.allow_own_tools = False
                turn_runtime._set_node(ctrl, orch.node_id, "running", wait="tool")
                messages.append(
                    LlmMessage(
                        role="assistant",
                        content=result.content,
                        tool_calls=result.tool_calls,
                    )
                )
                for call in result.tool_calls:
                    body, fact, ok_tool = turn_runtime._dispatch_tool(
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
                    messages.append(
                        LlmMessage(
                            role="tool",
                            content=body,
                            tool_call_id=call.id or None,
                            name=call.name or None,
                        )
                    )
                    if ok_tool:
                        memory.orch_failed_tools = 0
                        memory.orch_failed_thinks = 0
                        continue
                    memory.orch_failed_tools += 1
                    if memory.orch_failed_tools < MAX_ORCHESTRATOR_FAILED_TOOLS:
                        continue
                    if memory.orch_failed_thinks >= MAX_ORCHESTRATOR_FAILED_THINKS:
                        action = _fail_orch_tools(
                            ctrl, orch.node_id, memory.orch_failed_tools
                        )
                        return action
                    memory.orch_failed_thinks += 1
                    memory.orch_failed_tools = 0
                    memory.allow_own_tools = True
                    emit_log(
                        "warn",
                        "run.orchestrator.toolThink",
                        node_id=orch.node_id,
                        payload={
                            "failed": MAX_ORCHESTRATOR_FAILED_TOOLS,
                            "round": memory.orch_failed_thinks,
                        },
                    )
                    memory.add_note(_TOOL_THINK_NOTE)
                    messages.append(LlmMessage(role="user", content=_TOOL_THINK_NOTE))
                    break
                continue
            if result.tool_calls:
                offered = []
                memory.allow_own_tools = False
                raw = _control_raw(result)
                if not raw.strip():
                    repairs += 1
                    _log_repair(orch.node_id, "empty", raw)
                    if repairs <= MAX_CONTROL_REPAIRS:
                        memory.add_note(_TOOL_DECIDE_NOTE)
                        messages.append(LlmMessage(role="user", content=_TOOL_DECIDE_NOTE))
                        continue
                    action = _give_up(block_reply)
                    return action
            raw = _control_raw(result)
            reason = reject_reason(raw)
            if reason:
                memory.reject(raw, reason)
                repairs += 1
                _log_repair(orch.node_id, reason, raw)
                if repairs <= MAX_CONTROL_REPAIRS:
                    memory.add_note(_REPAIR_NOTE)
                    messages.append(LlmMessage(role="user", content=_REPAIR_NOTE))
                    continue
                action = _give_up(block_reply)
                return action
            parsed = parse_orchestrator_action(raw)
            kind = parsed.get("action") or "reply"
            if kind == "reply" and block_reply:
                action = {
                    "action": "think",
                    "text": parsed.get("text") or "",
                    "agent": "",
                    "task": "",
                    "source": "",
                }
                return _tag_tokens(action, result, out_final)
            if kind == "call":
                token = parsed.get("agent") or ""
                agent_id = match_agent(token, names)
                if agent_id is None:
                    repairs += 1
                    emit_log(
                        "warn",
                        "run.orchestrator.unknownAgent",
                        node_id=orch.node_id,
                        payload={"token": token},
                    )
                    if repairs <= MAX_CONTROL_REPAIRS:
                        note = dispatch._unknown_agent_note(token, names)
                        memory.add_note(note)
                        messages.append(LlmMessage(role="user", content=note))
                        continue
                    action = _give_up(block_reply)
                    return action
                source = memory.resolve_source(parsed.get("source") or "", names)
                if source.missing or source.ambiguous:
                    repairs += 1
                    emit_log(
                        "warn",
                        "run.orchestrator.unknownSource",
                        node_id=orch.node_id,
                        payload={"source": parsed.get("source") or ""},
                    )
                    if repairs <= MAX_CONTROL_REPAIRS:
                        note = dispatch._source_repair_note(source, memory)
                        memory.add_note(note)
                        messages.append(LlmMessage(role="user", content=note))
                        continue
                    action = {
                        "action": "think",
                        "text": "",
                        "agent": "",
                        "task": "",
                        "source": "",
                    }
                    return _tag_tokens(action, result, out_final)
                parsed["agent"] = agent_id
            if kind in {"call", "ask", "reply", "finish"}:
                memory.orch_failed_tools = 0
                memory.orch_failed_thinks = 0
            action = parsed
            return _tag_tokens(action, result, out_final)
        return None
    finally:
        if not (action and action.get("action") in {"think", "defer"}):
            turn_runtime._set_llm(ctrl, compiled, llm_node_id, busy=False)

