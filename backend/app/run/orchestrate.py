"""Decisions for the orchestrator node. The run chat is the only user-facing voice."""

from __future__ import annotations

import json

_ACTIONS = {"ask", "call", "reply", "finish"}


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
If a missing detail would change the task, ask the user before calling.
You may answer yourself when no agent is needed. Domain work belongs to the agents.
Write ask, reply, and finish text in the user's language.
Use reply when the user may want to continue. Use finish only when the task is done and the run should stop.
Reply with one JSON object and no other text:
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
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(text[start : end + 1])
        except ValueError:
            value = None
        if isinstance(value, dict) and value.get("action") in _ACTIONS:
            return {
                "action": str(value.get("action")),
                "text": str(value.get("text") or ""),
                "agent": str(value.get("agent") or ""),
                "task": str(value.get("task") or ""),
            }
    return {"action": "reply", "text": raw.strip(), "agent": "", "task": ""}


def match_agent(token: str, agents: list[tuple[str, str]]) -> str | None:
    raw = token.strip()
    if not raw:
        return None
    folded = raw.casefold()
    for agent_id, name in agents:
        if folded == agent_id.casefold() or (name and folded == name.casefold()):
            return agent_id
    return None
