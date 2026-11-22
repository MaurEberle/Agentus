"""Which of its own tools the orchestrator gets on a turn.

Reading files is always open (list, read, tree, stat, search): the orchestrator
checks what its agents did instead of judging old reads.

Everything else (changing files, terminal, web search, zip, HTTP, MCP) opens
after an agent call failed, during a takeover, or when the orchestrator asks
for it after a failure. It stays open until the next agent call. With the
terminal open from the start, a weak model built the whole app itself instead
of calling one agent (Dev Team run, 2026-11-17).
"""

from __future__ import annotations

import json

from app.tools.file_access_tool import FILE_ACTION_ORDER

READ_TOOL_KINDS = frozenset({"file_access"})
READ_FILE_ACTIONS = frozenset({"list", "stat", "read", "read_many", "search", "tree"})

WRITE_LOCKED_DETAIL = (
    "Changing files is not open to you now. Agents change files; you get write access "
    "after an agent call failed or during a takeover. Read and check freely, then call an agent "
    "with the change."
)
NOT_OFFERED_DETAIL = (
    "This tool is not open to you on this turn. Call only a tool listed under Connected tools as available."
)
TERMINAL_LOCKED_DETAIL = (
    "The terminal opens for you only after an agent call failed. Setup, builds and tests are the agents' work: "
    "call an agent."
)

_LATER_LABELS = {
    "terminal": "the terminal",
    "web_search": "web search",
    "http": "HTTP",
    "zip": "zip",
    "datetime": "date",
    "calculator": "the calculator",
}


def later_labels(orch, read_schemas: list[dict], full_schemas: list[dict]) -> list[str]:
    """What opens after a failure, in words, and only what this orchestrator has."""
    from app.run import turn_runtime

    read_names = set(turn_runtime._function_names(read_schemas))
    labels: list[str] = []
    for schema in full_schemas:
        function = schema.get("function") or {}
        name = str(function.get("name") or "")
        if name == "file_access":
            props = (function.get("parameters") or {}).get("properties") or {}
            enum = (props.get("action") or {}).get("enum") or []
            if any(action not in READ_FILE_ACTIONS for action in enum):
                labels.append("file changes")
            continue
        if name in read_names:
            continue
        if "__" in name:
            if "MCP tools" not in labels:
                labels.append("MCP tools")
            continue
        label = _LATER_LABELS.get(name)
        if label and label not in labels:
            labels.append(label)
    return labels


# Decisions as native tools. A tool-tuned model with tools offered answers with a tool
# call, never with the JSON decision; it read one file 43 times while writing "now I
# call the Junior" (Dev Team run, 2026-11-17). These four let it decide in tool mode.
DECISION_TOOLS: dict[str, str] = {
    "call_agent": "call",
    "ask_user": "ask",
    "reply": "reply",
    "finish": "finish",
}


def decision_schemas() -> list[dict]:
    def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": required,
                    "properties": properties,
                },
            },
        }

    text = {"type": "string", "description": "In the user's language."}
    return [
        _fn(
            "call_agent",
            "Decide: send one short task to one agent. The runtime runs the agent and shows you its result. "
            "Ends your turn.",
            {
                "agent": {"type": "string", "description": "Name or id from the roster."},
                "task": {"type": "string", "description": "A short instruction of a few sentences."},
                "source": {
                    "type": "string",
                    "description": 'Optional: id or name of an agent whose stored text is attached, or "none".',
                },
                "retry": {"type": "boolean", "description": "True when the same agent answered with text only."},
            },
            ["agent", "task"],
        ),
        _fn("ask_user", "Decide: ask the user a question and wait for the answer. Ends your turn.", {"text": text}, ["text"]),
        _fn("reply", "Decide: tell the user something in the chat without waiting. Ends your turn.", {"text": text}, ["text"]),
        _fn(
            "finish",
            "Decide: end the run with this final message, only when the task is done. Ends your turn.",
            {"text": text},
            ["text"],
        ),
    ]


def decision_from_calls(calls) -> tuple[str, str] | None:
    """``(tool name, decision JSON)`` for the first decision tool call, or None."""
    for call in calls or []:
        name = str(call.name or "")
        action = DECISION_TOOLS.get(name)
        if action is None:
            continue
        try:
            args = json.loads(call.arguments or "{}")
        except ValueError:
            args = {}
        if not isinstance(args, dict):
            args = {}
        decision: dict = {"action": action}
        if action == "call":
            decision["agent"] = str(args.get("agent") or "")
            decision["task"] = str(args.get("task") or "")
            if args.get("source"):
                decision["source"] = str(args.get("source"))
            if args.get("retry") is True:
                decision["retry"] = True
        else:
            decision["text"] = str(args.get("text") or "")
        return name, json.dumps(decision, ensure_ascii=False)
    return None


def call_key(name: str, arguments: str) -> tuple[str, str]:
    """A call's identity in one decision: tool name plus arguments, key order ignored."""
    try:
        value = json.loads(arguments or "{}")
    except ValueError:
        return name, " ".join((arguments or "").split())
    return name, json.dumps(value, sort_keys=True, ensure_ascii=False)


def read_file_actions(file_actions: list[str] | None) -> list[str]:
    base = list(FILE_ACTION_ORDER) if file_actions is None else list(file_actions)
    return [action for action in base if action in READ_FILE_ACTIONS]


def schemas(orch, *, write_open: bool) -> list[dict]:
    """Tool schemas for this turn. Without write access only the reading subset."""
    from app.run import turn_runtime

    if write_open:
        return turn_runtime._tool_schemas(
            orch.tool_kinds,
            orch.mcp,
            orch.file_actions,
            terminal_programs=orch.terminal_programs,
            terminal_unrestricted=orch.terminal_unrestricted,
        )
    kinds = [kind for kind in orch.tool_kinds if kind in READ_TOOL_KINDS]
    return turn_runtime._tool_schemas(
        kinds,
        [],
        read_file_actions(orch.file_actions),
        terminal_programs=orch.terminal_programs,
        terminal_unrestricted=orch.terminal_unrestricted,
    )


def file_action(arguments: str) -> str:
    try:
        value = json.loads(arguments or "{}")
    except ValueError:
        return ""
    if not isinstance(value, dict):
        return ""
    return str(value.get("action") or "").strip().lower()


def locked(call_name: str, arguments: str, offered_names: list[str], *, write_open: bool) -> tuple[str, str] | None:
    """``(error_key, detail)`` when this call is not open on this turn, else None.

    The schema already lists only open tools and actions, but models call what they
    remember. Nothing that is not open may run.
    """
    if call_name not in offered_names:
        if call_name == "terminal" and not write_open:
            return "tool.notOffered", TERMINAL_LOCKED_DETAIL
        return "tool.notOffered", NOT_OFFERED_DETAIL
    if call_name == "file_access" and not write_open:
        action = file_action(arguments)
        if action and action not in READ_FILE_ACTIONS:
            return "tool.writeLocked", WRITE_LOCKED_DETAIL
    return None
