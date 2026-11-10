"""Shrink an agent transcript before the next model call.

Duplicate tool results and a reply that filled the window are not sent again.
A model summary runs only when that is still not enough. The system prompt and
the latest tool result stay in place until the latest result itself is larger
than the window.
"""

from __future__ import annotations

import json

from app.run import window as run_window
from app.runtime.completions import estimate_token_count
from app.runtime.models import ChatMessage as LlmMessage

TRUNCATED_NOTE = (
    "The last reply was cut off at the output or context limit and was discarded. "
    "Continue from the task and the latest tool result. Act now: one tool call or a short answer. "
    "Do not repeat the discarded draft."
)

_SUPERSEDED = "Earlier result for {name} {path}: superseded."
_READ_ACTIONS = frozenset({"read", "list", "stat"})
_PATH_KEYS = ("path", "fileAbsolutePath", "filePath", "file", "workbook")


def held_window(llm, memory) -> int | None:
    """Window already chosen for this model. None before the first call."""
    tag = llm.model or ""
    for source in (memory.raised, memory.loaded):
        value = source.get(tag)
        if isinstance(value, int) and value > 0:
            return value
    if isinstance(llm.num_ctx, int) and llm.num_ctx > 0:
        return llm.num_ctx
    return None


def _reserve(llm, memory) -> int:
    thinking = bool(memory.thinking.get(llm.model or ""))
    return run_window.prompt_need([], llm.max_tokens, thinking=thinking)


def transcript_need(messages: list[LlmMessage], llm, memory) -> int:
    """Estimate that does not under-count dense tool JSON."""
    thinking = bool(memory.thinking.get(llm.model or ""))
    counted = run_window.prompt_need(messages, llm.max_tokens, thinking=thinking)
    chars = sum(len(message.content or "") for message in messages)
    for message in messages:
        for call in message.tool_calls or []:
            chars += len(call.name or "") + len(call.arguments or "")
    conservative = (chars + 2) // 3 + _reserve(llm, memory)
    return max(counted, conservative)


def window_pressure(
    messages: list[LlmMessage],
    llm,
    memory,
    *,
    last_prompt_tokens: int | None = None,
    last_context_max: int | None = None,
) -> bool:
    """True when the next call would have no room left for an answer."""
    held = held_window(llm, memory)
    if held is None:
        return False
    if transcript_need(messages, llm, memory) > held:
        return True
    if (
        last_prompt_tokens is not None
        and last_context_max is not None
        and last_prompt_tokens + _reserve(llm, memory) > last_context_max
    ):
        return True
    return False


def compact_transcript(messages: list[LlmMessage], *, budget: int) -> bool:
    """Drop replayed bulk. Returns True when a message changed."""
    changed = _supersede_duplicates(messages)
    changed = _shrink_read_history(messages) or changed
    changed = _drop_oversized_drafts(messages, budget) or changed
    if transcript_tokens(messages) + 1 > budget:
        changed = _digest_large_tools(messages, budget) or changed
    return changed


def transcript_tokens(messages: list[LlmMessage]) -> int:
    return estimate_token_count(
        "\n".join(
            (message.content or "")
            + "".join((call.arguments or "") for call in message.tool_calls or [])
            for message in messages
        )
    )


def state_transcript(messages: list[LlmMessage], *, clip: int = 1500) -> str:
    lines: list[str] = []
    for message in messages:
        text = message.content or ""
        if len(text) > clip:
            text = text[:clip] + "…"
        if message.tool_calls:
            names = ", ".join(call.name or "" for call in message.tool_calls)
            text = f"{text}\n[tool calls: {names}]".strip()
        lines.append(f"{message.role}: {text}")
    return "\n".join(lines)


def rewrite_with_state(messages: list[LlmMessage], state: str) -> list[LlmMessage]:
    """Keep the system prompt, the task, and the latest tool result."""
    system = [message for message in messages if message.role == "system"]
    first_user = next((message for message in messages if message.role == "user"), None)
    tail = _latest_tool_exchange(messages)
    kept: list[LlmMessage] = list(system)
    if first_user is not None and first_user not in tail:
        kept.append(first_user)
    kept.append(LlmMessage(role="user", content="Compacted state:\n" + state.strip()))
    kept.extend(tail)
    return kept


def _latest_tool_exchange(messages: list[LlmMessage]) -> list[LlmMessage]:
    last = next((index for index in range(len(messages) - 1, -1, -1) if messages[index].role == "tool"), None)
    if last is None:
        return []
    start = last
    if start > 0 and messages[start - 1].role == "assistant" and messages[start - 1].tool_calls:
        start -= 1
    end = last + 1
    while end < len(messages) and messages[end].role == "tool":
        end += 1
    return list(messages[start:end])


def _supersede_duplicates(messages: list[LlmMessage]) -> bool:
    slots = _tool_slots(messages)
    groups: dict[tuple[str, str], list[int]] = {}
    for index, name, args in slots:
        groups.setdefault((name, args), []).append(index)
    changed = False
    for (name, args), indexes in groups.items():
        if len(indexes) < 2:
            continue
        path = _path_of(args)
        stub = _SUPERSEDED.format(name=_leaf(name) or "tool", path=path).strip()
        for index in indexes[:-1]:
            if messages[index].content == stub:
                continue
            messages[index] = messages[index].model_copy(update={"content": stub})
            changed = True
    return changed


def _shrink_read_history(messages: list[LlmMessage]) -> bool:
    slots = _tool_slots(messages)
    groups: dict[str, list[int]] = {}
    for index, name, args in slots:
        read, path = _read_target(name, args)
        if not read or not path:
            continue
        groups.setdefault(path, []).append(index)
    changed = False
    for path, indexes in groups.items():
        if len(indexes) < 2:
            continue
        stub = _SUPERSEDED.format(name="read", path=path)
        for index in indexes[:-1]:
            if messages[index].content == stub:
                continue
            messages[index] = messages[index].model_copy(update={"content": stub})
            changed = True
    return changed


def _drop_oversized_drafts(messages: list[LlmMessage], budget: int) -> bool:
    """A draft larger than the answer reserve is the previous overflow."""
    if budget <= 0:
        return False
    changed = False
    for index, message in enumerate(messages):
        if message.role != "assistant" or message.tool_calls:
            continue
        text = message.content or ""
        if text == TRUNCATED_NOTE:
            continue
        if estimate_token_count(text) * 4 < budget:
            continue
        messages[index] = message.model_copy(update={"content": TRUNCATED_NOTE})
        changed = True
    return changed


def _digest_large_tools(messages: list[LlmMessage], budget: int) -> bool:
    if budget <= 0:
        return False
    changed = False
    # Leave the newest tool result until everything else is small.
    tool_indexes = [index for index, message in enumerate(messages) if message.role == "tool"]
    order = tool_indexes[:-1] + tool_indexes[-1:]
    for index in order:
        if transcript_tokens(messages) + 1 <= budget:
            break
        message = messages[index]
        text = message.content or ""
        limit = max(400, min(1600, budget // 4))
        if estimate_token_count(text) <= limit:
            continue
        digested = _digest_body(text, limit * 4)
        if digested == text:
            continue
        messages[index] = message.model_copy(update={"content": digested})
        changed = True
    return changed


def _tool_slots(messages: list[LlmMessage]) -> list[tuple[int, str, str]]:
    pending: list[tuple[str, str, str]] = []
    slots: list[tuple[int, str, str]] = []
    for index, message in enumerate(messages):
        if message.role == "assistant" and message.tool_calls:
            pending = [(call.id or "", call.name or "", call.arguments or "") for call in message.tool_calls]
            continue
        if message.role != "tool":
            continue
        name = message.name or ""
        args = ""
        call_id = message.tool_call_id or ""
        match = next((item for item in pending if item[0] and item[0] == call_id), None)
        if match is None and pending:
            match = pending.pop(0)
        elif match is not None:
            pending = [item for item in pending if item is not match]
        if match is not None:
            name = name or match[1]
            args = match[2]
        slots.append((index, name, args))
    return slots


def _leaf(name: str) -> str:
    if "__" in name:
        return name.rsplit("__", 1)[-1]
    return name


def _path_of(args: str) -> str:
    data = _args(args)
    for key in _PATH_KEYS:
        value = data.get(key)
        if value:
            return str(value)
    return ""


def _read_target(name: str, args: str) -> tuple[bool, str]:
    data = _args(args)
    action = str(data.get("action") or "").lower()
    leaf = _leaf(name).lower()
    path = _path_of(args)
    read = action in _READ_ACTIONS or any(part in leaf for part in ("read", "describe", "list"))
    return read, path


def _args(raw: str) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _digest_body(text: str, limit: int) -> str:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return text[:limit] + "…"
    shaped = _shape(value)
    if len(shaped) <= limit:
        return shaped
    return shaped[:limit] + "…"


def _shape(value: object) -> str:
    if isinstance(value, list):
        head = value[:2]
        keys = ""
        if head and isinstance(head[0], dict):
            keys = ", ".join(str(key) for key in list(head[0])[:12])
        return f"{len(value)} rows. columns: {keys}. sample: {json.dumps(head, ensure_ascii=False)[:800]}"
    if isinstance(value, dict):
        rows = value.get("rows") or value.get("values") or value.get("data")
        if isinstance(rows, list):
            return f"keys: {', '.join(str(key) for key in list(value)[:12])}. {_shape(rows)}"
        return f"keys: {', '.join(str(key) for key in list(value)[:20])}"
    return str(value)[:800]
