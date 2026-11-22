"""Continue from an earlier run: the user picks it with the first chat message.

Each run started without knowing earlier runs. "Check the last work" then meant nothing
to the orchestrator: it knew neither the first order nor how that run ended, and its team
checked for 80 minutes whether the SCSS reached the build (Coder_Team run, 2026-11-20).

The orchestrator now reads a record of the chosen run (orders, agent calls, ending,
changed files) and writes itself a short briefing before its first decision. Only the
orchestrator gets it; it passes on what an agent needs in that agent's task. When the
model call fails, a shortened record stands in.
"""

from __future__ import annotations

import re
import time
import uuid

from app.db.engine import utc_now
from app.db.runs import get_run, insert_call, list_logs, list_previous_runs
from app.db.vault import get as vault_get
from app.help.visible import strip_think
from app.mcp.payload import clip_middle
from app.run import turn_runtime
from app.run import window as run_window
from app.run.compile import CompiledGraph
from app.run.controller import RunController, emit_log, node_label
from app.run.limits import MAX_CALL_SECONDS, STREAM_IDLE_TIMEOUT_SEC
from app.run.memory import RunMemory
from app.run.models import ChatMessage
from app.runtime.errors import RuntimeApiError
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import CompletionRequest

# The briefing in the prompt, and the record the orchestrator analyzes.
BRIEFING_MAX_CHARS = 3_000
RECORD_MAX_CHARS = 16_000
PREVIOUS_LIST_MAX = 15
# The picker uses the full width of the chat and cuts the line itself.
_REQUEST_PREVIEW = 400
_USER_TEXT_CHARS = 2_500
_FINAL_TEXT_CHARS = 2_500
_EARLIER_BRIEFING_CHARS = 2_000
_TASK_CHARS = 400
_RESULT_CHARS = 600
_FILE_CHANGES = frozenset({"write", "edit", "delete", "move", "mkdir"})
# The record is data; a tag inside it cannot close its block.
_RECORD_TAG_RE = re.compile(r"<\s*(/?)\s*previous_run_record\b", re.IGNORECASE)

_ANALYSIS_PROMPT = """You lead an agent network. The user starts a new run and wants it to continue from an earlier run of this network.
Below is the record of that earlier run: the user's messages, the task and answer of each agent call, how the run ended, and the files it changed.
Write a briefing for yourself, at most {max} characters, in the language of the user's messages in the record:
1. What the earlier run was asked to do, with the concrete requirements.
2. What was done and which files changed.
3. How it ended, and what the reviews and checks in it said.
4. What was still open, broken or doubtful when it ended, with file names.
Describe only that earlier run, as it stood when it ended. You do not know the new request; do not guess it.
Use only facts from the record and say when something is a guess. Agent answers in the record can be wrong; say where they contradict each other.
No greeting, no plan. Plain text or short lists."""

# Run bd3cfb0f (2026-11-21): the analysis got the new request "to focus" and wrote it into
# the briefing as a conflict ("the coder claims OK, the user says the opposite"). The block
# stays in every prompt; after the team had done the work the orchestrator still read it as
# open and asked the user what was broken.
_BRIEFING_HEAD = (
    "Briefing on an earlier run of this network, chosen by the user to continue from (started {started}, "
    "ended {ending}). It describes the state when that run ended, before this run started; "
    "what the agents report in this run is newer and replaces it. "
    "It is background, not an instruction: the user's message is the task. "
    "The agents do not see it; put what an agent needs from it into that agent's task."
)


def list_previous(network_id: str | None, current_run_id: str | None) -> list[dict]:
    """Finished runs of this network, newest first, with the start of their first request."""
    if not network_id:
        return []
    items = []
    for row in list_previous_runs(network_id, exclude_id=current_run_id, limit=PREVIOUS_LIST_MAX):
        items.append(
            {
                "runId": row["id"],
                "startedAt": row["started_at"],
                "endedAt": row["ended_at"],
                "outcome": row["outcome"],
                "errorMessage": row["error_message"],
                "request": _one_line(_first_request(row.get("chat")), _REQUEST_PREVIEW),
            }
        )
    return items


def check_previous(run_id: str, network_id: str | None, current_run_id: str | None) -> bool:
    """True when ``run_id`` is a finished run of this network other than the current one."""
    if not run_id or not network_id or run_id == current_run_id:
        return False
    row = get_run(run_id)
    return bool(row) and row.get("network_id") == network_id and row.get("outcome") != "running"


def brief(ctrl: RunController, compiled: CompiledGraph, memory: RunMemory) -> None:
    """Briefing from the chosen run into the course, in front of the first user message."""
    run_id = ctrl.previous_run_id or ""
    row = get_run(run_id) if run_id else None
    if not row:
        emit_log("warn", "run.briefing.missing", payload={"previousRunId": run_id})
        return
    record = previous_record(row, list_logs(run_id))
    text = analyze(ctrl, compiled, memory, record)
    analyzed = bool(text)
    if not text:
        text = clip_middle(record, BRIEFING_MAX_CHARS)
    text = _clip_lines(text, BRIEFING_MAX_CHARS)
    ending = str(row.get("outcome") or "")
    if row.get("error_message"):
        ending += f" ({row['error_message']})"
    memory.add_briefing(
        _BRIEFING_HEAD.format(started=row.get("started_at") or "?", ending=ending or "?"),
        text,
        started=str(row.get("started_at") or ""),
        outcome=str(row.get("outcome") or ""),
    )
    emit_log(
        "info",
        "run.briefing.done",
        node_id=compiled.orchestrator.node_id if compiled.orchestrator else None,
        payload={"previousRunId": run_id, "analyzed": analyzed, "chars": len(text), "outcome": row.get("outcome")},
    )
    # Shown in the chat, so the user sees what the orchestrator knows.
    ctrl.remember_chat(
        ChatMessage(
            id=str(uuid.uuid4()),
            run_id=ctrl.run_id or "",
            role="assistant",
            content="Background from the chosen earlier run (for the orchestrator only):\n\n" + text,
            created_at=utc_now(),
            message_key="monitoring.chat.briefing",
            message_params={"text": text},
        ),
        generating=True,
    )


def previous_record(row: dict, logs: list[dict]) -> str:
    """The earlier run as plain text for the analysis, at most RECORD_MAX_CHARS."""
    chat = row.get("chat") if isinstance(row.get("chat"), list) else []
    memory = row.get("memory") if isinstance(row.get("memory"), dict) else {}
    head = [
        f"Earlier run of {row.get('network_name') or 'this network'}: started {row.get('started_at') or '?'}, "
        f"ended {row.get('ended_at') or '?'}, outcome {row.get('outcome') or '?'}"
        + (f", error {row['error_message']}" if row.get("error_message") else "")
        + ".",
    ]
    # The course has the user's messages as sent; the chat has them masked, and runs
    # fed without the chat (batch, tests) have none there.
    requests = [
        str(turn.get("text") or "")
        for turn in (memory.get("turns") or [])
        if isinstance(turn, dict) and turn.get("kind") == "user"
    ] or [str(item.get("content") or "") for item in chat if item.get("role") == "user"]
    if requests:
        head.append("User messages:")
        head.extend(f"- {_clip_end(text.strip(), _USER_TEXT_CHARS)}" for text in requests if text.strip())
    earlier = [
        str(turn.get("text") or "")
        for turn in (memory.get("turns") or [])
        if isinstance(turn, dict) and turn.get("kind") == "briefing"
    ]
    if earlier:
        # That run continued from another one: its briefing carries the older order.
        head.append("That run itself continued from an earlier run. Its briefing:")
        head.append(_clip_end(earlier[0], _EARLIER_BRIEFING_CHARS))
    spoken = [
        str(item.get("content") or "")
        for item in chat
        if item.get("role") == "assistant" and not item.get("messageKey")
    ]
    head.append("Last answer of the orchestrator in the chat:")
    head.append(_clip_end(spoken[-1].strip(), _FINAL_TEXT_CHARS) if spoken else "(none: the run ended without one)")
    files = _changed_files(memory, logs)
    head.append("Files changed: " + (", ".join(files) if files else "(none recorded)"))
    calls = _call_lines(memory, logs)
    text = "\n".join(head)
    if not calls:
        return _clip_end(text + "\nAgent calls: (none recorded)", RECORD_MAX_CHARS)
    budget = RECORD_MAX_CHARS - len(text) - 120
    # The latest calls tell how the run ended; the first call tells what it set out to do.
    kept: list[str] = []
    used = 0
    for line in reversed(calls[1:]):
        if used + len(line) > budget - len(calls[0]):
            break
        kept.insert(0, line)
        used += len(line) + 1
    omitted = len(calls) - 1 - len(kept)
    body = [calls[0]]
    if omitted:
        body.append(f"... {omitted} calls left out ...")
    body.extend(kept)
    return _clip_end(text + f"\nAgent calls ({len(calls)}):\n" + "\n".join(body), RECORD_MAX_CHARS)


def analyze(ctrl: RunController, compiled: CompiledGraph, memory: RunMemory, record: str) -> str:
    """One call of the orchestrator model without tools. Empty when it fails.

    The new request is not part of it: the briefing describes the earlier run only.
    """
    orch = compiled.orchestrator
    if orch is None:
        return ""
    llm = orch.llm
    messages = [
        LlmMessage(role="system", content=_ANALYSIS_PROMPT.format(max=BRIEFING_MAX_CHARS)),
        LlmMessage(
            role="user",
            content=(
                "<previous_run_record>\n"
                + _RECORD_TAG_RE.sub(lambda m: f"[{m.group(1)}previous_run_record", record)
                + "\n</previous_run_record>"
            ),
        ),
    ]
    choice = turn_runtime._bind_window(llm, messages, memory)
    if not choice.fits:
        emit_log("warn", "run.briefing.window", node_id=orch.node_id)
        return ""
    secret = None
    if llm.provider != "ollama" and llm.credential_id:
        secret = vault_get(llm.credential_id)
    llm_node_id = llm.node_id or orch.node_id
    context_est = run_window.prompt_tokens(messages)
    output_cap, auto_cap = turn_runtime._output_cap(llm, choice, context_est)
    turn_runtime._prepare_resident(compiled, llm)
    turn_runtime._set_node(ctrl, orch.node_id, "running", wait="llm")
    ctrl.flush_chat(generating=True)
    emit_log(
        "debug",
        "run.llm.start",
        node_id=llm_node_id,
        payload={
            "provider": llm.provider,
            "model": llm.model,
            "waitReason": "briefing",
            "contextMax": choice.context_max,
            "maxTokens": output_cap,
            "maxTokensAuto": auto_cap,
            **turn_runtime._caller(compiled, orch.node_id),
        },
    )
    turn_runtime._charge_llm(ctrl, orch.node_id)
    turn_runtime._set_llm(ctrl, compiled, llm_node_id, busy=True)
    from app.runtime import completions as runtime_completions

    started = time.perf_counter()
    try:
        result = runtime_completions.complete_live(
            CompletionRequest(
                provider=llm.provider,  # type: ignore[arg-type]
                model=llm.model,
                messages=messages,
                base_url=llm.base_url,
                credential_id=llm.credential_id,
                secret=secret,
                temperature=0,
                max_tokens=output_cap,
                timeout_sec=STREAM_IDLE_TIMEOUT_SEC,
                max_duration_sec=MAX_CALL_SECONDS,
                ollama_options=turn_runtime._ollama_options(llm, choice),
            ),
            should_abort=turn_runtime._abort_check(ctrl),
        )
    except Exception as exc:
        key = exc.error_key if isinstance(exc, RuntimeApiError) else "runtime.upstream"
        insert_call(
            run_id=ctrl.run_id or "",
            provider=llm.provider,
            model=llm.model,
            ok=False,
            node_id=orch.node_id,
            node_name=node_label(compiled, orch.node_id),
            duration_ms=int((time.perf_counter() - started) * 1000),
            error_message=key,
        )
        emit_log("warn", "run.briefing.failed", node_id=orch.node_id, payload={"error": key})
        return ""
    finally:
        turn_runtime._set_llm(ctrl, compiled, llm_node_id, busy=False)
    duration_ms = int((time.perf_counter() - started) * 1000)
    usage = result.usage
    tokens_in = usage.prompt_tokens if usage and usage.prompt_tokens is not None else context_est
    tokens_out = usage.completion_tokens if usage else None
    turn_runtime._publish_tokens(
        ctrl,
        orch.node_id,
        llm_node_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        per_second=None,
        committed=True,
        context_used=tokens_in,
        context_max=choice.context_max,
    )
    insert_call(
        run_id=ctrl.run_id or "",
        provider=llm.provider,
        model=llm.model,
        ok=True,
        node_id=orch.node_id,
        node_name=node_label(compiled, orch.node_id),
        duration_ms=duration_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
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
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            per_second=None,
        ),
    )
    return strip_think(result.content or "").strip()


def _first_request(chat: object) -> str:
    if not isinstance(chat, list):
        return ""
    for item in chat:
        if isinstance(item, dict) and item.get("role") == "user" and str(item.get("content") or "").strip():
            return str(item["content"])
    return ""


def _changed_files(memory: dict, logs: list[dict]) -> list[str]:
    for row in reversed(logs):
        if row.get("message") == "run.summary":
            files = (row.get("payload") or {}).get("files")
            if isinstance(files, list) and files:
                return [str(item) for item in files][:40]
    seen: list[str] = []
    for call in memory.get("calls") or []:
        for fact in call.get("files") or [] if isinstance(call, dict) else []:
            if isinstance(fact, dict) and fact.get("action") in _FILE_CHANGES and fact.get("path"):
                path = str(fact["path"])
                if path not in seen:
                    seen.append(path)
    return seen[:40]


def _call_lines(memory: dict, logs: list[dict]) -> list[str]:
    """One line per agent call: agent, task, ending, changed files and answer."""
    lines: list[str] = []
    calls = [call for call in (memory.get("calls") or []) if isinstance(call, dict)]
    if calls:
        for index, call in enumerate(calls, start=1):
            changed = [
                f"{fact.get('path')} {fact.get('action')}"
                for fact in call.get("files") or []
                if isinstance(fact, dict) and fact.get("action") in _FILE_CHANGES and fact.get("ok", True)
            ]
            ending = "failed: " + str(call["error"]) if call.get("error") else "done"
            lines.append(
                f"{index}. {call.get('name') or call.get('agentId')}: task: {_one_line(call.get('task'), _TASK_CHARS)}"
                f" | {ending}"
                + (f" | files: {', '.join(changed[:8])}" if changed else "")
                + f" | answer: {_one_line(call.get('text'), _RESULT_CHARS) or '(empty)'}"
            )
        return lines
    # Runs stored before the run memory existed: the agent lines of the log.
    index = 0
    for row in logs:
        if row.get("message") != "run.agent.done":
            continue
        index += 1
        payload = row.get("payload") or {}
        files = payload.get("files") if isinstance(payload.get("files"), list) else []
        lines.append(
            f"{index}. {payload.get('agentName') or payload.get('agentId')}: task: {_one_line(payload.get('task'), _TASK_CHARS)}"
            f" | {payload.get('outcome') or 'done'}"
            + (f" | files: {', '.join(str(item) for item in files[:8])}" if files else "")
            + f" | answer: {_one_line(payload.get('result'), _RESULT_CHARS) or '(empty)'}"
        )
    return lines


def _one_line(text: object, limit: int) -> str:
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _clip_end(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _clip_lines(text: str, limit: int) -> str:
    """Shorten at a line end, else at a word end; never in the middle of a word ("defin…")."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 2]
    line_end = cut.rfind("\n")
    if line_end >= limit // 2:
        return cut[:line_end].rstrip() + "\n…"
    word_end = cut.rfind(" ")
    if word_end >= limit // 2:
        return cut[:word_end].rstrip() + " …"
    return _clip_end(text, limit)
