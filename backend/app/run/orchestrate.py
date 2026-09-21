"""Decisions for the orchestrator node. The run chat is the only user-facing voice."""

from __future__ import annotations

import json
import re

from app.help.visible import strip_think

_ACTIONS = {"ask", "call", "reply", "finish"}
_ACTION_RE = re.compile(r'"action"\s*:\s*"(ask|call|reply|finish)"')
_PROSE_CALL = re.compile(r"^call\s+(\S+)\s+with\s+(.+)$", re.IGNORECASE | re.DOTALL)
# A salvaged task longer than this is a pasted document with broken quotes, not an instruction.
_MAX_SALVAGED_TASK = 500


def orchestrator_instructions(user_prompt: str, agents: list[tuple[str, str, str]]) -> str:
    lines: list[str] = []
    for agent_id, name, instructions in agents:
        brief = " ".join(instructions.split())[:400]
        lines.append(f"- id: {agent_id}\n  name: {name}\n  instructions: {brief or '(none)'}")
    roster = "\n".join(lines) if lines else "(no agents connected)"
    protocol = f"""You orchestrate this agent network.
You are the only voice in the run chat. Agents do not speak to the user.
Each agent below is one private channel. A call sends one task down that channel and returns one result to you.
The agent sees only that task, not this chat.
Call one agent at a time, wait for the result, then decide again. You may call the same agent later with a new task.
The task field is a short instruction of a few sentences. Do not paste an earlier agent result into it.
The runtime attaches the latest agent result to the next agent for you.
If a missing detail would change the task, ask the user before calling.
You may answer yourself when no agent is needed. Domain work belongs to the agents.
Write ask, reply, and finish text in the user's language.
Use reply when the user may want to continue. Use finish only when the task is done and the run should stop.
Reply with one JSON object and no other text. Do not describe the call in a sentence:
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


def parse_orchestrator_action(raw: str) -> dict[str, str]:
    text = _prepare(raw)
    parsed = _parse_json_object(text)
    if parsed is not None:
        return parsed
    salvaged = _salvage(text)
    if salvaged is not None:
        return salvaged
    prose = _prose_call(text)
    if prose is not None:
        return prose
    return {"action": "reply", "text": text, "agent": "", "task": ""}


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
    text = strip_think(raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _parse_json_object(text: str) -> dict[str, str] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except ValueError:
        return None
    if isinstance(value, dict) and value.get("action") in _ACTIONS:
        return _action(
            str(value.get("action")),
            str(value.get("text") or ""),
            str(value.get("agent") or ""),
            str(value.get("task") or ""),
        )
    return None


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
        return _action(action, "", agent_found[0].strip(), task.strip())
    spoken = _closed_string(text, "text")
    if spoken is None:
        return None
    return _action(action, spoken[0].strip(), "", "")


def _prose_call(text: str) -> dict[str, str] | None:
    match = _PROSE_CALL.match(text.strip())
    if not match:
        return None
    agent = match.group(1).strip().strip("\"'")
    task = match.group(2).strip()
    if not agent or not task:
        return None
    return _action("call", "", agent, task)


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


def _action(action: str, text: str, agent: str, task: str) -> dict[str, str]:
    return {"action": action, "text": text, "agent": agent, "task": task}


def match_agent(token: str, agents: list[tuple[str, str]]) -> str | None:
    raw = token.strip()
    if not raw:
        return None
    folded = raw.casefold()
    for agent_id, name in agents:
        if folded == agent_id.casefold() or (name and folded == name.casefold()):
            return agent_id
    return None
