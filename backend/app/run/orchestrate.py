"""Decisions for the orchestrator node. The run chat is the only user-facing voice."""

from __future__ import annotations

import json
import re

from app.help.visible import strip_think, think_inner
from app.runtime.models import ToolCall

_ACTIONS = {"ask", "call", "reply", "finish", "think"}
_ACTION_RE = re.compile(r'"action"\s*:\s*"(ask|call|reply|finish|think)"')
# A salvaged task longer than this is a pasted document with broken quotes, not an instruction.
_MAX_SALVAGED_TASK = 500


def orchestrator_instructions(
    user_prompt: str,
    agents: list[tuple[str, str, str]],
    tool_names: list[str] | None = None,
) -> str:
    lines: list[str] = []
    for agent_id, name, instructions in agents:
        brief = " ".join(instructions.split())[:400]
        lines.append(f"- id: {agent_id}\n  name: {name}\n  instructions: {brief or '(none)'}")
    roster = "\n".join(lines) if lines else "(no agents connected)"
    names = [name for name in (tool_names or []) if name]
    tool_block = ""
    if names:
        tool_block = (
            "You have tools: "
            + ", ".join(names)
            + ".\n"
            "Call a tool with a tool call. Do not put a tool call in the JSON object and do not describe it in a sentence.\n"
            "Use tools to check files after an agent. Do not use tools instead of calling an agent.\n"
            "At most two tool rounds this step, then one JSON object.\n"
            "After the tool result, decide again with one JSON object.\n"
            "A later step sees only short lines for your own tools, not the tool result.\n"
        )
    protocol = f"""You orchestrate this agent network.
You are the only voice in the run chat. Agents do not speak to the user.
Each agent below is one private channel. A call sends one short task down that channel and returns one result to the runtime.
After a call you see a status line (name, id, finished, character count, file lines) and the result of that call.
The run keeps the full course in memory. That course is not in this prompt. Older results stay in memory.
When an agent fails, the runtime adds one anomaly excerpt for that agent only. The following step does not keep it.
Call one agent at a time, wait for the result, then decide again. You may call the same agent later with a new task.
Call by the name or id in the roster below.
The task field is a short instruction of a few sentences. Do not paste an agent result into it.
To attach an agent's stored text, set source to that agent's id or name. You write the id, not the text. The runtime attaches the stored text, including from an agent that has tools. Omit source, or leave it empty, to send only the task.
If a missing detail would change the task, ask and wait. Do not write that you might ask. If the task is clear, call.
A reply is shown in the chat. After a reply, the next JSON must be think, call, ask, or finish. Do not reply again. Do not announce a call in a reply; emit the call object. Domain work belongs to the agents.
Use think for internal planning. Think is not shown in the chat and does not count against the step limit. After think, emit call, ask, or finish.
A status line without a successful write or delete means no file was written or deleted. An agent that returned text completed that text. File work belongs to agents that write or delete. Before finish, those files must exist.
Write ask, reply, think, and finish text in the user's language.
Use ask for a question that needs an answer. Use reply to speak without waiting. Use finish only when the task is done and the run should stop.
{tool_block}Reply with one JSON object and no other text. Do not describe the call in a sentence:
{{"action":"think","text":"..."}}
{{"action":"ask","text":"..."}}
{{"action":"call","agent":"<id or name>","task":"..."}}
{{"action":"reply","text":"..."}}
{{"action":"finish","text":"..."}}

Agents:
{roster}
"""
    extra = user_prompt.strip()
    if extra:
        return extra + "\n\n" + protocol
    return protocol


def control_source(content: str, reasoning: str = "") -> str:
    """Visible text wins. Empty visible falls back to think JSON, then provider reasoning."""
    raw = content or ""
    if strip_think(raw).strip():
        return raw
    inner = think_inner(raw).strip()
    if inner and looks_like_control(inner):
        return raw
    return (reasoning or "").strip()


def agent_think_text(content: str, reasoning: str = "", *, has_tools: bool = False) -> str | None:
    """Internal planning for an agent turn. Visible prose is a result, not think."""
    raw = content or ""
    visible = strip_think(raw).strip()
    blob = visible or think_inner(raw).strip() or (reasoning or "").strip()
    if blob:
        parsed = parse_orchestrator_action(blob)
        if parsed.get("action") == "think":
            if has_tools and visible:
                return None
            return (parsed.get("text") or "").strip() or "…"
    if visible:
        return None
    hidden = think_inner(raw).strip() or (reasoning or "").strip()
    if hidden:
        return hidden
    return None


def parse_orchestrator_action(raw: str) -> dict[str, str]:
    text = _prepare(raw)
    parsed = _parse_json_object(text)
    if parsed is not None:
        return parsed
    salvaged = _salvage(text)
    if salvaged is not None:
        return salvaged
    prose = _salvage_prose_call(text)
    if prose is not None:
        return prose
    return {"action": "reply", "text": text, "agent": "", "task": "", "source": ""}


def reject_reason(raw: str) -> str | None:
    """Unreadable control text is discarded. The body must not re-enter a prompt."""
    visible = _prepare(raw)
    if not visible:
        return "empty"
    structured = _parse_json_object(visible)
    action = parse_orchestrator_action(visible)
    kind = action.get("action") or "reply"
    if kind == "reply" and structured is None and looks_like_control(visible):
        return "unreadable"
    if kind in {"ask", "reply", "finish"} and not (action.get("text") or "").strip():
        return "empty"
    if kind == "think":
        return None
    if kind == "call" and not (action.get("agent") or "").strip():
        return "empty"
    return None


def looks_like_control(text: str) -> bool:
    folded = text.strip().lower()
    if not folded:
        return False
    if folded.startswith("{") or folded.startswith("```"):
        return True
    if folded.startswith("call "):
        return True
    return '"action"' in folded and any(f'"{name}"' in folded for name in _ACTIONS)


def _prepare(raw: str) -> str:
    source = raw or ""
    visible = strip_think(source).strip()
    if visible:
        text = visible
    else:
        inner = think_inner(source).strip()
        text = inner if inner and looks_like_control(inner) else ""
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_json_object(text: str) -> dict[str, str] | None:
    start = text.find("{")
    if start < 0:
        return None
    try:
        value, _end = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    if isinstance(value, dict) and value.get("action") in _ACTIONS:
        return _action(
            str(value.get("action")),
            str(value.get("text") or ""),
            str(value.get("agent") or ""),
            str(value.get("task") or ""),
            str(value.get("source") or ""),
        )
    return None


_PROSE_CALL = re.compile(
    r"^call\s+([^\s,.:;]+)(?:\s+with\s+|\s+to\s+|,\s*|:\s*|\s+[—–-]\s+|\s+)(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_PROSE_CALL_BARE = re.compile(r"^call\s+([^\s,.:;]+)\s*$", re.IGNORECASE)


def _salvage_prose_call(text: str) -> dict[str, str] | None:
    folded = (text or "").strip()
    if not folded.lower().startswith("call "):
        return None
    match = _PROSE_CALL.match(folded)
    if match:
        agent = match.group(1).strip().strip("\"'`")
        task = match.group(2).strip()
        if agent and len(task) <= _MAX_SALVAGED_TASK:
            return _action("call", "", agent, task, "")
        return None
    match = _PROSE_CALL_BARE.match(folded)
    if not match:
        return None
    agent = match.group(1).strip().strip("\"'`")
    if not agent:
        return None
    return _action("call", "", agent, "", "")


def _salvage(text: str) -> dict[str, str] | None:
    found = _ACTION_RE.search(text)
    if not found:
        return None
    action = found.group(1)
    if action == "call":
        agent_found = _closed_string(text, "agent")
        if agent_found is None or not agent_found[0].strip():
            return None
        task_found = _closed_string(text, "task")
        if task_found is None:
            task = ""
        else:
            task, task_end = task_found
            rest = text[task_end:].lstrip()
            # An inner quote closed the string early and the story continues after it.
            if rest and not rest.startswith(("}", ",")):
                return None
        if len(task) > _MAX_SALVAGED_TASK:
            return None
        source_found = _closed_string(text, "source")
        source = source_found[0].strip() if source_found else ""
        return _action(action, "", agent_found[0].strip(), task.strip(), source)
    spoken = _closed_string(text, "text")
    if spoken is None:
        return None
    return _action(action, spoken[0].strip(), "", "", "")


def _closed_string(text: str, name: str) -> tuple[str, int] | None:
    match = re.search(rf'"{name}"\s*:\s*"', text)
    if not match:
        return None
    chars: list[str] = []
    index = match.end()
    while index < len(text):
        char = text[index]
        if char == "\\":
            if index + 1 >= len(text):
                return None
            nxt = text[index + 1]
            chars.append({"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
            index += 2
            continue
        if char == '"':
            return "".join(chars), index + 1
        chars.append(char)
        index += 1
    return None


def _action(action: str, text: str, agent: str, task: str, source: str = "") -> dict[str, str]:
    return {"action": action, "text": text, "agent": agent, "task": task, "source": source}


_TOOL_CALL_BLOCK = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL | re.IGNORECASE)
_FUNCTION_EQ = re.compile(r"<function=([^>\s]+)>(.*?)</function>", re.DOTALL | re.IGNORECASE)
_ARG_PAIR = re.compile(
    r"<arg_key>\s*([^<]+?)\s*</arg_key>\s*<arg_value>(.*?)</arg_value>",
    re.DOTALL | re.IGNORECASE,
)
_PARAM_EQ = re.compile(
    r"<parameter=([^>]+)>(.*?)</parameter>",
    re.DOTALL | re.IGNORECASE,
)


def salvage_tool_calls(content: str, offered: list[str] | None = None) -> list[ToolCall]:
    """Turn a complete XML tool_call / function= block into native tool calls."""
    text = content or ""
    names = offered or []
    found: list[ToolCall] = []
    for match in _TOOL_CALL_BLOCK.finditer(text):
        call = _tool_call_from_block(match.group(1), names, len(found))
        if call is not None:
            found.append(call)
    for match in _FUNCTION_EQ.finditer(text):
        call = _tool_call_from_named(match.group(1), match.group(2), names, len(found))
        if call is not None:
            found.append(call)
    return found


def _tool_call_from_block(inner: str, offered: list[str], index: int) -> ToolCall | None:
    blob = (inner or "").strip()
    if not blob:
        return None
    try:
        value = json.loads(blob)
    except ValueError:
        value = None
    if isinstance(value, dict):
        fn = value.get("function") if isinstance(value.get("function"), dict) else None
        name = str((fn or value).get("name") or "")
        args = (fn or value).get("arguments", value.get("parameters"))
        if args is None:
            args = {key: val for key, val in value.items() if key not in {"name", "function"}}
        return _make_tool_call(name, args, offered, index)
    name, rest = _leading_tool_name(blob)
    pairs = {key.strip(): val for key, val in _ARG_PAIR.findall(rest)}
    if not pairs:
        pairs = {key.strip(): val for key, val in _PARAM_EQ.findall(rest)}
    if name and pairs:
        return _make_tool_call(name, pairs, offered, index)
    return None


def _tool_call_from_named(name: str, inner: str, offered: list[str], index: int) -> ToolCall | None:
    pairs = {key.strip(): val for key, val in _PARAM_EQ.findall(inner or "")}
    if not pairs:
        pairs = {key.strip(): val for key, val in _ARG_PAIR.findall(inner or "")}
    if not (name or "").strip() or not pairs:
        return None
    return _make_tool_call(name, pairs, offered, index)


def _leading_tool_name(blob: str) -> tuple[str, str]:
    lines = blob.splitlines()
    first = (lines[0] if lines else blob).strip()
    if first.startswith("{") or first.startswith("<"):
        return "", blob
    return first, "\n".join(lines[1:]) if lines else ""


def _make_tool_call(name: str, args: object, offered: list[str], index: int) -> ToolCall | None:
    resolved = _resolve_tool_name(name, offered)
    if not resolved:
        return None
    if isinstance(args, str):
        arguments = args
    else:
        try:
            arguments = json.dumps(args if args is not None else {}, ensure_ascii=False)
        except (TypeError, ValueError):
            return None
    return ToolCall(id=f"salvage_{index + 1}", name=resolved, arguments=arguments)


def _resolve_tool_name(raw: str, offered: list[str]) -> str:
    name = (raw or "").strip().strip("\"'`")
    if not name:
        return ""
    if name in offered:
        return name
    hits: list[str] = []
    for item in offered:
        leaf = item.rsplit("__", 1)[-1] if "__" in item else item
        if leaf == name or item.endswith("__" + name):
            hits.append(item)
    uniq = list(dict.fromkeys(hits))
    if len(uniq) == 1:
        return uniq[0]
    return name


_ROLE_NOISE = frozenset(
    {
        "coder",
        "manager",
        "agent",
        "dev",
        "developer",
        "writer",
        "bot",
        "node",
        "role",
        "specialist",
        "engineer",
        "assistant",
    }
)


def match_agent(token: str, agents: list[tuple[str, str]]) -> str | None:
    raw = token.strip()
    if not raw:
        return None
    folded = raw.casefold()
    exact: list[str] = []
    for agent_id, name in agents:
        if folded == agent_id.casefold() or (name and folded == name.casefold()):
            exact.append(agent_id)
    uniq = list(dict.fromkeys(exact))
    if len(uniq) == 1:
        return uniq[0]
    if uniq:
        return None
    simplified = _role_key(folded)
    hits: list[str] = []
    for agent_id, name in agents:
        nid = agent_id.casefold()
        nname = (name or "").casefold()
        keys = {_role_key(nid), _role_key(nname), nid, nname}
        if simplified and simplified in keys:
            hits.append(agent_id)
            continue
        if _alias_hit(folded, simplified, nname):
            hits.append(agent_id)
    uniq = list(dict.fromkeys(hits))
    if len(uniq) == 1:
        return uniq[0]
    return None


def _role_key(text: str) -> str:
    parts = [part for part in re.split(r"[^a-z0-9]+", text.casefold()) if part and part not in _ROLE_NOISE]
    return " ".join(parts)


def _alias_hit(folded: str, simplified: str, name: str) -> bool:
    if not name or len(name) < 4:
        return False
    words = [part for part in re.split(r"[^a-z0-9]+", folded) if part]
    if name in words:
        return True
    if simplified and len(simplified) >= 4 and (name.startswith(simplified) or simplified.startswith(name)):
        return True
    return False
