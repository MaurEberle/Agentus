"""Shared live helpers for one run: tools, window, and node status.

Tests patch ``tools_execute``, ``get_mcp``, ``_set_llm``, and
``_inference_pool_bytes`` on this module.
"""

from __future__ import annotations

import logging
import time

from app.common.secrets import mask_obj
from app.db.engine import utc_now
from app.db.runs import upsert_step
from app.db.vault import get as vault_get
from app.mcp.payload import format_tool_result
from app.run import window as run_window
from app.run.compile import CompiledGraph
from app.run.controller import RunController, emit_log, node_label
from app.run.limits import LAST_MESSAGE_MAX
from app.run.mcp_bridge import get_mcp, map_openai_tool_name
from app.run.memory import (
    AgentRecord,
    FileFact,
    RunMemory,
    ToolEvent,
    file_fact,
    record_tool,
    reused_file_result,
)
from app.run.models import ActivityDag, ActivityTokens, NodeLlmInfo, NodeRuntime, NodeTokens
from app.run.orchestrate import salvage_tool_calls
from app.run.sse import publish
from app.runtime.completions import estimate_token_count
from app.runtime.errors import RuntimeApiError
from app.runtime.models import ChatMessage as LlmMessage
from app.runtime.models import CompletionResult
from app.tools import execute as tools_execute
from app.tools.catalog import openai_tools_for_kinds

log = logging.getLogger("agentus.run")

_SAME_RETRY = frozenset({"runtime.timeout", "runtime.unreachable", "runtime.upstream"})

_TRUNCATED_REASONS = frozenset({"length", "max_tokens", "truncated"})

_FILE_MUTATIONS = frozenset({"write", "delete", "edit", "move"})

_FILE_PREP_ACTIONS = frozenset({"read", "list", "stat", "mkdir", "search", "tree", "read_many"})


def _completion_log_payload(result: CompletionResult, extra: dict | None = None) -> dict:
    payload: dict = {
        "finishReason": result.finish_reason or "",
        "content": result.content or "",
        "reasoning": result.reasoning or "",
    }
    if extra:
        payload.update(extra)
    return payload

def _result_truncated(result: CompletionResult) -> bool:
    reason = (result.finish_reason or "").strip().lower()
    return reason in _TRUNCATED_REASONS

def _runtime_error_payload(exc: BaseException) -> dict | None:
    if not isinstance(exc, RuntimeApiError):
        return None
    payload: dict = {}
    if exc.detail:
        payload["detail"] = exc.detail
    if exc.status is not None:
        payload["status"] = exc.status
    return payload or None

def _tool_schemas(
    kinds: list[str],
    mcp_pairs: list[tuple[str, list[str] | None, str | None]],
    file_actions: list[str] | None = None,
    *,
    terminal_programs: list[str] | None = None,
    terminal_unrestricted: bool = False,
) -> list[dict]:
    tools = openai_tools_for_kinds(
        kinds,
        file_actions=file_actions,
        terminal_programs=terminal_programs,
        terminal_unrestricted=terminal_unrestricted,
    )
    bridge = get_mcp()
    if bridge and mcp_pairs:
        from app.run.mcp_bridge import mcp_openai_tools

        for server_id, allow, _cred in mcp_pairs:
            infos = bridge.listed_tools(server_id)
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

def _parse_args(raw: str) -> dict:
    import json

    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}

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
    leaf = mapped[1] if mapped else call_name
    reused = None
    if reuse and record is not None:
        if leaf == "file_access" or call_name == "file_access":
            reused = reused_file_result(
                record, str(args.get("action") or ""), str(args.get("path") or "")
            )
        else:
            preview = file_fact(leaf, args, {}, ok=True)
            if preview is not None and preview.path:
                reused = reused_file_result(record, preview.action, preview.path)
    if reused is not None:
        tool_result = reused
    elif mapped and mcp:
        from app.run.graph_models import is_mcp_node

        for edge in compiled.doc.edges:
            if edge.target != owner_id or edge.target_handle != "tool":
                continue
            src = compiled.by_id.get(edge.source)
            if (
                src
                and is_mcp_node(src)
                and str(src.data.get("mcpServerId") or "") == mapped[0]
            ):
                tool_node_id = src.id
                break
        if tool_node_id != owner_id:
            _set_node(ctrl, tool_node_id, "running", wait="tool", message=call_name)
        try:
            out = mcp.call(mapped[0], mapped[1], args)
            tool_result = out.get("result") if out.get("ok") else out
        finally:
            if tool_node_id != owner_id:
                _set_node(ctrl, tool_node_id, "idle")
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
    payload: dict = {"name": call_name, "waitReason": "tool", "ok": ok_tool}
    if isinstance(args, dict):
        import json as _json

        payload["arguments"] = _json.dumps(mask_obj(args), ensure_ascii=False)
    if isinstance(tool_result, dict) and not ok_tool:
        if tool_result.get("errorKey"):
            payload["errorKey"] = tool_result["errorKey"]
        err = tool_result.get("error") or tool_result.get("result")
        if err:
            payload["error"] = str(err)
    emit_log(
        "info" if ok_tool else "warn",
        "run.tool.call",
        node_id=tool_node_id,
        payload=payload,
    )
    fact = None if reused is not None else file_fact(leaf, args, tool_result, ok=ok_tool)
    masked = format_tool_result(mask_obj(tool_result))
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

def _with_salvaged_tools(result: CompletionResult, offered: list[dict] | None) -> CompletionResult:
    if result.tool_calls or not offered:
        return result
    calls = salvage_tool_calls(result.content or "", _function_names(offered))
    if not calls:
        return result
    return result.model_copy(update={"tool_calls": calls})

def _prepare_resident(compiled: CompiledGraph, llm) -> None:
    if getattr(llm, "provider", None) != "ollama" or not getattr(llm, "model", None):
        return
    from app.run.vram import release_others
    from app.settings.service import load_settings

    try:
        settings = load_settings()
        dropped = release_others(settings, compiled, current=llm.model)
    except Exception:
        return
    if dropped:
        emit_log(
            "info",
            "run.llm.release",
            payload={"dropped": dropped, "keep": llm.model},
        )

def _static_context_max(num_ctx: int | None) -> int | None:
    if isinstance(num_ctx, int) and num_ctx > 0:
        return num_ctx
    return None

def _inference_pool_bytes() -> int:
    from app.run.resources import latest

    gpus = list(latest().gpus or [])
    pool = [gpu for gpu in gpus if gpu.inference]
    if not pool:
        pool = [gpu for gpu in gpus if gpu.vram_total_bytes >= 512 * 1024 * 1024]
    if not pool and gpus:
        pool = [max(gpus, key=lambda gpu: gpu.vram_total_bytes)]
    return sum(max(0, gpu.vram_total_bytes) for gpu in pool)

def _display_count(value: object) -> str | int:
    if isinstance(value, bool) or value is None:
        return "—"
    if isinstance(value, int):
        return value
    return "—"

def _moe_auto_options(llm, choice, layers: int | None) -> dict:
    """Leave GPU placement to llama.cpp.

    Ollama 0.40 ignores ``num_cpu_moe`` and honors ``num_gpu``. Sending a
    partial ``num_gpu`` disables that fitter. The Qwen3.6 run then loaded
    12 of 41 layers, and the next attempt used ``num_gpu`` 0. The inspector
    estimate predicts the fitter. It is not sent as a layer command.
    """
    from app.runtime.vram_est import vram_profile

    del choice, layers
    profile = vram_profile(llm.model, base_url=llm.base_url)
    if profile is None or not profile.routed_expert_bytes:
        emit_log(
            "warn",
            "run.llm.moeUnsplit",
            node_id=getattr(llm, "node_id", None),
            payload={"model": llm.model},
        )
    return {}

def _log_vram_compare(llm, options, choice, node_id: str) -> None:
    if getattr(llm, "provider", None) != "ollama" or not getattr(llm, "model", None):
        return
    try:
        from app.runtime.ollama import loaded_memory
        from app.runtime.vram_est import estimate_vram_bytes, plan_moe_offload, vram_profile, with_kv_cache

        profile = with_kv_cache(vram_profile(llm.model, base_url=llm.base_url), getattr(llm, "kv_cache_type", None))
        num_ctx = choice.num_ctx if choice is not None and choice.num_ctx else 0
        opts = options if isinstance(options, dict) else {}
        num_gpu = opts.get("num_gpu")
        num_cpu = opts.get("num_cpu_moe")
        plan = (
            plan_moe_offload(profile, num_ctx=num_ctx, pool_bytes=_inference_pool_bytes())
            if profile is not None
            else None
        )
        estimated: int | None
        if plan is not None and (isinstance(num_cpu, int) or "num_gpu" not in opts):
            estimated = plan.estimated_gpu_bytes
        elif profile is not None:
            gpu = num_gpu if isinstance(num_gpu, int) and num_gpu > 0 else None
            estimated = estimate_vram_bytes(profile, num_ctx=num_ctx, num_gpu=gpu)
        else:
            estimated = None
        size, size_vram = loaded_memory(llm.model, base_url=llm.base_url)
        if estimated is None and size_vram is None:
            return
        delta = None if estimated is None or size_vram is None else size_vram - estimated
        payload = {
            "model": llm.model,
            "estimatedBytes": _display_count(estimated),
            "actualVramBytes": _display_count(size_vram),
            "actualBytes": _display_count(size),
            "deltaBytes": _display_count(delta),
            "expertsOnGpu": plan.experts_on_gpu if plan else "—",
            "expertLayers": plan.expert_layers if plan else "—",
            "attentionLayersOnGpu": plan.attention_layers_on_gpu if plan else "—",
            "numGpu": _display_count(num_gpu),
            "numCpuMoe": _display_count(num_cpu),
            "numCtx": num_ctx,
        }
        emit_log("info", "run.llm.vram", node_id=node_id, payload=payload)
        log.info(
            "vram compare model=%s estimated=%s actual_vram=%s delta=%s num_gpu=%s num_cpu_moe=%s",
            llm.model,
            estimated,
            size_vram,
            delta,
            num_gpu,
            num_cpu,
        )
    except Exception:
        log.exception("vram compare failed model=%s", getattr(llm, "model", ""))

def _ollama_options(llm, choice) -> dict | None:
    if llm.provider != "ollama":
        return None
    options: dict = {}
    if choice is not None and choice.num_ctx:
        options["num_ctx"] = choice.num_ctx
    if isinstance(llm.num_thread, int) and llm.num_thread > 0:
        options["num_thread"] = llm.num_thread
    if getattr(llm, "kv_cache_type", None) == "q8_0":
        options["kv_cache_type"] = "q8_0"
    wants_layers = isinstance(llm.num_gpu, int) and llm.num_gpu > 0
    wants_percent = isinstance(llm.num_gpu_percent, int) and llm.num_gpu_percent > 0
    placement = getattr(llm, "gpu_placement", None)
    from app.runtime.ollama import (
        clamp_gpu_layers,
        gpu_layers_for_percent,
        model_block_count,
        model_is_moe,
        moe_omits_num_gpu,
        ollama_num_gpu,
    )

    is_moe = model_is_moe(llm.model, base_url=llm.base_url)
    layers = model_block_count(llm.model, base_url=llm.base_url)
    offload = None
    if wants_layers:
        offload = clamp_gpu_layers(llm.num_gpu, layers)
    elif wants_percent:
        offload = gpu_layers_for_percent(llm.num_gpu_percent, layers)
    elif placement == "layers" and isinstance(layers, int) and layers > 0:
        offload = layers
    elif placement == "layers":
        offload = 999
    if is_moe and moe_omits_num_gpu(
        is_moe=True,
        placement=placement,
        offload_layers=offload,
        block_count=layers,
    ):
        options.update(_moe_auto_options(llm, choice, layers))
    elif offload is not None:
        options["num_gpu"] = ollama_num_gpu(offload, layers)
    return options or None

def _bind_window(llm, messages: list[LlmMessage], memory: RunMemory):
    preferred = llm.num_ctx if isinstance(llm.num_ctx, int) and llm.num_ctx > 0 else None
    tag = llm.model or ""
    loaded = None
    arch = None
    thinking = False
    if llm.provider == "ollama" and tag:
        if tag not in memory.arch:
            memory.arch[tag] = run_window.architecture_context(tag, base_url=llm.base_url)
        if tag not in memory.thinking:
            memory.thinking[tag] = run_window.model_thinking(tag, base_url=llm.base_url)
        if tag not in memory.loaded:
            memory.loaded[tag] = run_window.loaded_context(tag, base_url=llm.base_url)
        arch = memory.arch[tag]
        thinking = bool(memory.thinking.get(tag))
        loaded = memory.loaded[tag]
    need = run_window.prompt_need(messages, llm.max_tokens, thinking=thinking)
    choice = run_window.choose_window(
        need=need,
        preferred=preferred,
        loaded=loaded,
        raised=memory.raised.get(tag),
        architecture_max=arch,
        provider=llm.provider,
        thinking=thinking,
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
        update["last_message"] = cleaned[:LAST_MESSAGE_MAX] or None
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

