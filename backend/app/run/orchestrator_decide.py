"""One orchestrator model call: own tools, then one control decision."""

from __future__ import annotations

import json
import time
import traceback

from app.db.runs import insert_call
from app.db.vault import get as vault_get
from app.run import agent_turn, dispatch, orch_tools, turn_runtime
from app.run.context_watch import ContextWatch
from app.run import window as run_window
from app.run.compile import CompiledGraph
from app.run.controller import RunController, emit_log, node_label
from app.run.limits import (
    MAX_CONTROL_REPAIRS,
    MAX_ORCHESTRATOR_FAILED_THINKS,
    MAX_ORCHESTRATOR_FAILED_TOOLS,
    MAX_ORCHESTRATOR_TOOL_CALLS,
    MAX_CALL_SECONDS,
    MAX_REPEATED_CALLS,
    MAX_SAME_RETRIES,
    MAX_SAME_TOOL_ERRORS,
    STREAM_IDLE_TIMEOUT_SEC,
)
from app.run.memory import RunMemory, ToolEvent, clip_tool_messages
from app.help.visible import strip_think
from app.run.orchestrate import (
    asks_user,
    control_source,
    invented_tool_action,
    match_agent,
    parse_orchestrator_action,
    reject_reason,
    structured_action,
)
from app.run.turn_runtime import _SAME_RETRY
from app.runtime.completions import estimate_token_count
from app.runtime.errors import RuntimeApiError
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import CompletionRequest, CompletionResult

_REPAIR_NOTE = (
    "The last decision was discarded. It was not shown to the user and no agent was called. "
    "Reply with one JSON object and no other text. "
    "ask, reply, finish, and think need a non-empty text field. "
    "A call needs agent and a short task. Do not paste an agent result. Do not add tool-call tags."
)

_TOOL_DECIDE_NOTE = (
    "This turn needs one JSON decision. A tool call is not that decision. "
    "Reply with one JSON object."
)

_SLOW_NOTE = (
    "Your last answer took too long and was stopped. Decide now, briefly, with one JSON object."
)

_TOOL_CAP_NOTE = (
    "You used {n} tool calls in this step, which is the limit. No more tools in this step. "
    "Decide now with one JSON object."
)

_SKIP_STEP_LIMIT = "Not run: tool limit for this step reached."

_ORIENTATION_CAP_NOTE = (
    "You used {n} tool calls to look around before your first agent call, which is the limit. "
    "No more tools until you have called an agent. Decide now with one JSON object: call an agent or ask."
)

_WITHDRAWN_NOTE = (
    "{name} failed {count} times in a row with the same error ({error}). It is withdrawn for the rest of "
    "this decision. Decide with one JSON object, or use another tool."
)
_SKIP_WITHDRAWN = "Not run: this tool is withdrawn for the rest of this decision."

_REPEATED_DETAIL = (
    "Not run: you already made this exact call in this step and its result is above. "
    "Do not repeat it. Decide now: call_agent, ask_user, reply or finish, or one JSON object."
)

_REPEAT_WITHDRAWN_NOTE = (
    "{name} was called again with the same arguments {count} times. It is withdrawn for the rest of this "
    "decision. Decide now: call_agent, ask_user, reply or finish, or one JSON object."
)

_DECIDE_NOW_NOTE = (
    "Your tools are used up for this step, and a tool call written as text does not run. "
    "Decide now with one JSON object: call, ask, reply or finish."
)

_ANNOUNCE_NOTE = (
    'Your text "{text}" did not decide anything; no agent was called. When you are done checking, decide: '
    "call call_agent, ask_user, reply or finish, or answer with one JSON object."
)


def _error_of(body: str) -> str:
    """The error key of a failed tool answer, for the same-error count."""
    try:
        data = json.loads(body)
    except ValueError:
        return "failed"
    if not isinstance(data, dict):
        return "failed"
    return str(data.get("errorKey") or data.get("error") or "failed")
_SKIP_AFTER_FAILURES = "Not run: five tool calls failed in a row. Think first."

_TOOL_THINK_NOTE = (
    "Five tool calls failed in a row. Think, then decide with one JSON object or a working tool call. "
    "Do not repeat the same failed call."
)


def _from_reasoning(result: CompletionResult, raw: str) -> bool:
    """The control text came from provider reasoning because the visible answer was empty."""
    visible = strip_think(result.content or "").strip()
    return bool(raw.strip()) and not visible and raw.strip() == (result.reasoning or "").strip()

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
    if not block_reply:
        return {"action": "unreadable"}
    # After a reply the run does not fail at once; the loop counts these and
    # fails at MAX_UNREADABLE_STREAK instead of thinking forever.
    return {"action": "think", "_unreadable": "1"}


def _tool_request(verb: str, result: CompletionResult, out_final: int | None) -> dict[str, str]:
    """The model wrote a tool step as a JSON action. The loop decides what it may use."""
    action = {"action": "tool-request", "verb": verb, "text": "", "agent": "", "task": "", "source": ""}
    return _tag_tokens(action, result, out_final)


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
    write_open: bool = True,
    tool_cap: int | None = None,
    orientation: bool = False,
) -> dict[str, str] | None:
    orch = compiled.orchestrator
    if orch is None:
        return None
    cap = tool_cap or MAX_ORCHESTRATOR_TOOL_CALLS
    # Per tool: (error, count) of failures in a row in this decision; withdrawn tools.
    fail_streak: dict[str, tuple[str, int]] = {}
    withdrawn: set[str] = set()
    # Calls that already ran in this decision, and repeats per tool.
    answered: set[tuple[str, str]] = set()
    repeats: dict[str, int] = {}
    announced = False
    repairs = 0
    model_retries = 0
    offered = list(tools)
    messages = memory.orchestrator_messages(system)
    base_len = len(messages)
    mcp = turn_runtime.get_mcp()
    llm_node_id = orch.llm.node_id or orch.node_id
    action: dict[str, str] | None = None
    own_calls = 0
    own_failed = 0
    slow_retries = 0
    decision_started = time.perf_counter()
    via = "json"
    try:
        while not ctrl.stop_event.is_set():
            offered = turn_runtime._available_tools(ctrl, compiled, orch.node_id, offered)
            # With own tools offered, the decisions are tools too; without, JSON only.
            decision_tools = orch_tools.decision_schemas() if offered else []
            choice = turn_runtime._bind_window(orch.llm, messages, memory)
            cuts: list[str] = []
            while not choice.fits:
                # O7: shorten the course step by step, oldest results first, instead of
                # ending the run. Tasks and changed files of every call stay. Messages of
                # this decision (tool calls and results) are kept; the last step shortens
                # their tool results.
                cut = memory.compact_step()
                if cut is None:
                    break
                cuts.append(cut)
                extras = messages[base_len:]
                if memory.clip_tools:
                    extras = clip_tool_messages(extras)
                base = memory.orchestrator_messages(system)
                base_len = len(base)
                messages = base + extras
                choice = turn_runtime._bind_window(orch.llm, messages, memory)
            if cuts:
                emit_log("info", "run.orchestrator.trimmed", node_id=orch.node_id, payload=memory.trim_payload(cuts))
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
            output_cap, auto_cap = turn_runtime._output_cap(llm, choice, context_est)
            turn_runtime._prepare_resident(compiled, llm)
            emit_log(
                "debug",
                "run.llm.start",
                node_id=llm_node_id,
                payload={
                    "provider": llm.provider,
                    "model": llm.model,
                    "waitReason": "llm",
                    "contextMax": context_max,
                    "promptEst": context_est,
                    "maxTokens": output_cap,
                    "maxTokensAuto": auto_cap,
                    **turn_runtime._caller(compiled, orch.node_id),
                },
            )
            from app.runtime import completions as runtime_completions

            repaired = turn_runtime._close_open_tool_calls(messages)
            if repaired:
                emit_log("warn", "run.llm.toolCallsRepaired", node_id=orch.node_id, payload={"count": repaired})
            turn_runtime._charge_llm(ctrl, orch.node_id)
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
                        max_tokens=output_cap,
                        tools=(offered + decision_tools) or None,
                        timeout_sec=STREAM_IDLE_TIMEOUT_SEC,
                        max_duration_sec=MAX_CALL_SECONDS,
                        ollama_options=options,
                    ),
                    should_abort=turn_runtime._abort_check(ctrl),
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
                if key == "runtime.generationLimit" and slow_retries < 1:
                    # R1: one more chance with a nudge to be brief; a second overrun ends the run.
                    slow_retries += 1
                    emit_log("warn", key, node_id=orch.node_id, payload=turn_runtime._runtime_error_payload(exc))
                    messages.append(LlmMessage(role="user", content=_SLOW_NOTE))
                    continue
                if key in _SAME_RETRY and model_retries < MAX_SAME_RETRIES:
                    model_retries += 1
                    emit_log("warn", key, node_id=orch.node_id)
                    continue
                if isinstance(exc, RuntimeApiError) and key in _SAME_RETRY:
                    # O14: the model is away, the course is intact. The loop pauses instead of failing.
                    emit_log("warn", key, node_id=orch.node_id, payload=turn_runtime._runtime_error_payload(exc))
                    action = {"action": "llm-unavailable", "text": key, "agent": "", "task": "", "source": ""}
                    return action
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
            in_final = usage.prompt_tokens if usage and usage.prompt_tokens is not None else context_est
            # Only the edge check: the prompt is rebuilt from memory for every decision.
            cut = ContextWatch(detect_drops=False).observe(
                reported=usage.prompt_tokens if usage else None, estimate=context_est, context_max=context_max
            )
            if cut is not None:
                emit_log(
                    "warn",
                    "run.llm.contextCut",
                    node_id=llm_node_id,
                    payload={"model": llm.model, **cut, **turn_runtime._caller(compiled, orch.node_id)},
                )
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
                "info",
                "run.llm.done",
                node_id=llm_node_id,
                payload=turn_runtime._llm_done_payload(
                    compiled,
                    orch.node_id,
                    llm,
                    result,
                    duration_ms=duration_ms,
                    tokens_in=in_final,
                    tokens_out=out_final,
                    per_second=rate_final,
                ),
            )
            # Decision tools written as text are read even when no tool is offered.
            result = turn_runtime._with_salvaged_tools(result, offered + orch_tools.decision_schemas())
            decided = orch_tools.decision_from_calls(result.tool_calls)
            if decided is not None:
                # A decision tool ends the turn; other calls in this answer do not run.
                emit_log(
                    "info",
                    "run.orchestrator.decisionTool",
                    node_id=orch.node_id,
                    payload={"name": decided[0], "dropped": len(result.tool_calls) - 1},
                )
                result = result.model_copy(update={"tool_calls": [], "content": decided[1], "reasoning": ""})
                via = "tool"
            if result.tool_calls and offered:
                model_retries = 0
                # Write access stays open until the next agent call (dispatch resets it).
                open_names = turn_runtime._function_names(offered)
                turn_runtime._set_node(ctrl, orch.node_id, "running", wait="tool")
                messages.append(
                    LlmMessage(
                        role="assistant",
                        content=result.content,
                        tool_calls=result.tool_calls,
                    )
                )
                think_round = False
                notes: list[str] = []
                visible = strip_think(result.content or "").strip()
                if visible and not announced:
                    # "Now I call the Junior" next to a tool call: say that nothing was decided.
                    announced = True
                    notes.append(_ANNOUNCE_NOTE.format(text=" ".join(visible.split())[:160]))
                for call in result.tool_calls:
                    if (call.name or "") in withdrawn:
                        turn_runtime._skip_tool_call(messages, call, "tool.withdrawn", _SKIP_WITHDRAWN)
                        continue
                    key = orch_tools.call_key(call.name or "", call.arguments or "")
                    if key in answered:
                        # The same call again: its result is already above. It does not run.
                        name = call.name or ""
                        repeats[name] = repeats.get(name, 0) + 1
                        turn_runtime._skip_tool_call(messages, call, "tool.repeated", _REPEATED_DETAIL)
                        emit_log("warn", "run.orchestrator.toolRepeated", node_id=orch.node_id, payload={"name": name})
                        if repeats[name] >= MAX_REPEATED_CALLS and name not in withdrawn:
                            withdrawn.add(name)
                            offered = [
                                item for item in offered if (item.get("function") or {}).get("name") != name
                            ]
                            emit_log(
                                "warn",
                                "run.orchestrator.toolWithdrawn",
                                node_id=orch.node_id,
                                payload={"name": name, "error": "tool.repeated"},
                            )
                            notes.append(_REPEAT_WITHDRAWN_NOTE.format(name=name, count=repeats[name]))
                        continue
                    if think_round:
                        # Five failed in a row: stop running calls, but answer every id (O5).
                        turn_runtime._skip_tool_call(messages, call, "tool.skipped", _SKIP_AFTER_FAILURES)
                        continue
                    if own_calls >= cap:
                        turn_runtime._skip_tool_call(messages, call, "tool.stepLimit", _SKIP_STEP_LIMIT)
                        continue
                    own_calls += 1
                    if orientation:
                        memory.orientation_calls += 1
                    closed = orch_tools.locked(
                        call.name or "", call.arguments or "", open_names, write_open=write_open
                    )
                    if closed is not None:
                        # Not run: the schema did not offer it on this turn.
                        error_key, detail = closed
                        body = json.dumps({"ok": False, "error": error_key, "detail": detail})
                        fact, ok_tool = None, False
                        emit_log(
                            "warn",
                            "run.orchestrator.toolLocked",
                            node_id=orch.node_id,
                            payload={"name": call.name or "", "error": error_key},
                        )
                    else:
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
                    if closed is None:
                        # A locked call ran nothing; it is no progress and no file fact.
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
                        fail_streak.pop(call.name or "", None)
                        answered.add(key)
                        continue
                    own_failed += 1
                    if turn_runtime._call_refused(ctrl, compiled, orch.node_id, call.name):
                        # A maxCalls refusal is the network's choice, not a broken tool.
                        continue
                    tool_name = call.name or ""
                    error = _error_of(body)
                    previous = fail_streak.get(tool_name)
                    count = previous[1] + 1 if previous and previous[0] == error else 1
                    fail_streak[tool_name] = (error, count)
                    if count >= MAX_SAME_TOOL_ERRORS and tool_name not in withdrawn:
                        # Same tool, same error, again and again: stop offering it in this decision.
                        withdrawn.add(tool_name)
                        offered = [
                            item for item in offered if (item.get("function") or {}).get("name") != tool_name
                        ]
                        emit_log(
                            "warn",
                            "run.orchestrator.toolWithdrawn",
                            node_id=orch.node_id,
                            payload={"name": tool_name, "error": error},
                        )
                        notes.append(_WITHDRAWN_NOTE.format(name=tool_name, count=count, error=error))
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
                    think_round = True
                if think_round:
                    # The note follows all tool answers; a user turn between them is invalid.
                    memory.add_note(_TOOL_THINK_NOTE)
                    messages.append(LlmMessage(role="user", content=_TOOL_THINK_NOTE))
                for note in notes:
                    messages.append(LlmMessage(role="user", content=note))
                if own_calls >= cap and offered:
                    offered = []
                    if orientation:
                        emit_log(
                            "warn",
                            "run.orchestrator.orientationCap",
                            node_id=orch.node_id,
                            payload={"calls": memory.orientation_calls},
                        )
                        messages.append(
                            LlmMessage(role="user", content=_ORIENTATION_CAP_NOTE.format(n=memory.orientation_calls))
                        )
                    else:
                        emit_log(
                            "warn",
                            "run.orchestrator.toolCap",
                            node_id=orch.node_id,
                            payload={"calls": own_calls, "max": cap},
                        )
                        messages.append(LlmMessage(role="user", content=_TOOL_CAP_NOTE.format(n=own_calls)))
                continue
            if result.tool_calls:
                offered = []
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
            if own_calls >= cap and invented_tool_action(raw):
                # Tools used up for this step, and the model writes the next call as text:
                # not to the chat, and not a new step with a fresh budget. Decide now.
                memory.reject(raw, "tool")
                repairs += 1
                _log_repair(orch.node_id, "toolText", raw)
                if repairs <= MAX_CONTROL_REPAIRS:
                    messages.append(LlmMessage(role="user", content=_DECIDE_NOW_NOTE))
                    continue
                # Not unreadable: the model clearly wants more tool steps than this decision
                # had (run 4f895701 ended here after a green build). The loop gives the next
                # decision a new budget; the idle guard still stops endless re-reading.
                action = _tool_request(invented_tool_action(raw) or "read", result, out_final)
                action["_overBudget"] = str(own_calls)
                return action
            reason = reject_reason(raw)
            if reason:
                verb = invented_tool_action(raw)
                if verb:
                    memory.reject(raw, "tool")
                    return _tool_request(verb, result, out_final)
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
            if kind in {"think", "reply", "ask", "finish"}:
                # A file change or command pasted into the text: never shown, never a plan
                # the loop keeps repeating. The loop opens the matching tools or says why not.
                verb = invented_tool_action(parsed.get("text") or "")
                if verb:
                    return _tool_request(verb, result, out_final)
            if kind == "reply" and _from_reasoning(result, raw) and not structured_action(raw):
                # O10: provider reasoning is private planning; it must never reach the chat.
                emit_log("info", "run.orchestrator.privateReasoning", node_id=orch.node_id)
                action = {"action": "think", "text": parsed.get("text") or "", "agent": "", "task": "", "source": ""}
                return _tag_tokens(action, result, out_final)
            if kind == "reply" and asks_user(parsed.get("text") or ""):
                # A question needs an answer: the run waits instead of deciding on and asking again.
                emit_log("info", "run.orchestrator.replyAsAsk", node_id=orch.node_id)
                parsed["action"] = kind = "ask"
            if kind == "reply" and block_reply:
                action = {
                    "action": "think",
                    "text": parsed.get("text") or "",
                    "agent": "",
                    "task": "",
                    "source": "",
                    # The loop tells the model why this text never reached the chat.
                    "_blocked": "reply",
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
                # O16: keep what the model wrote next to the resolved id for the log.
                parsed["agentToken"] = token
            if kind in {"call", "ask", "reply", "finish"}:
                memory.orch_failed_tools = 0
                memory.orch_failed_thinks = 0
            parsed["_via"] = via
            action = parsed
            return _tag_tokens(action, result, out_final)
        return None
    finally:
        if not (action and action.get("action") in {"think", "defer"}):
            turn_runtime._set_llm(ctrl, compiled, llm_node_id, busy=False)
        if own_calls:
            # B8: a decision that used tools, in one line: how many, how long, how it ended.
            emit_log(
                "info",
                "run.orchestrator.step",
                node_id=orch.node_id,
                payload={
                    "calls": own_calls,
                    "failed": own_failed,
                    "durationMs": int((time.perf_counter() - decision_started) * 1000),
                    "end": (action or {}).get("action") or ("stopped" if ctrl.stop_event.is_set() else "none"),
                    "capped": own_calls >= cap,
                    "withdrawn": sorted(withdrawn),
                    "orientation": orientation,
                },
            )

