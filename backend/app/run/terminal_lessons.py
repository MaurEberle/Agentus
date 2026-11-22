"""Terminal commands an agent may not send, and what it uses instead.

Coder_Team run, 2026-11-20: 174 terminal commands of one agent were rejected, in all
19 of its calls. 71 were a kind already rejected in an earlier call (each call starts
a new conversation), 47 came back in the same call after other steps (the hint sat in
an old tool result). The prompt named the allowed programs but not what to use for
cat, grep or mkdir, and not that inline code is rejected.

Two parts:
- ``alternatives``: a short list in the terminal block of the system prompt, before
  any mistake, naming only replacements the agent really has.
- ``note`` / ``block_for``: each rejected kind once, as a line in the agent's system
  prompt. It stays there for the rest of the call and starts every later call of the
  same agent in this run.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

# Rejections that are about the command, not about the setup.
LESSON_KEYS = frozenset(
    {
        "tools.terminal.notGranted",
        "tools.terminal.inlineCode",
        "tools.terminal.shellSyntax",
        "tools.terminal.outsideRoot",
    }
)
MAX_LESSONS = 6
_EXAMPLE_CHARS = 60
_BLOCK_HEAD = (
    "# Rejected earlier in this run\n"
    "These terminal commands were rejected. Do not send them or similar ones again; use what is named:"
)

# Habit programs by what they do; the first names are shown in the prompt.
_HABITS: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("read", ("cat", "type", "head", "tail", "more", "less", "get-content", "gc"), 4),
    ("search", ("grep", "findstr", "select-string", "rg", "ack", "sls"), 2),
    ("list", ("ls", "dir", "find", "tree", "get-childitem", "gci", "where"), 3),
    ("mkdir", ("mkdir", "md", "new-item"), 1),
    ("delete", ("rm", "del", "rmdir", "rd", "remove-item", "erase"), 2),
    ("move", ("mv", "move", "ren", "rename", "move-item"), 1),
    ("copy", ("cp", "copy", "xcopy", "robocopy", "copy-item"), 1),
    ("write", ("echo", "touch", "printf", "set-content", "out-file", "tee"), 2),
    ("cd", ("cd", "pwd", "chdir", "pushd", "set-location"), 2),
)
_GROUP_OF = {name: group for group, names, _ in _HABITS for name in names}


@dataclass
class FileReach:
    """The file actions an agent can use, from its file_access node."""

    actions: list[str]
    write: bool
    delete: bool


def _replacement(group: str, files: FileReach | None, root: str) -> str:
    if group == "cd":
        return f"not needed; every command runs in {root}"
    if files is None:
        return "not available; you have no file tool"
    have = set(files.actions)
    if group == "read" and "read" in have:
        return "file_access read (head, tail, offset and limit pick lines)"
    if group == "search" and "search" in have:
        return "file_access search with text (pattern picks the files)"
    if group == "list":
        found = [name for name in ("list", "tree", "search") if name in have]
        if found:
            names = found[0] if len(found) == 1 else ", ".join(found[:-1]) + " or " + found[-1]
            return "file_access " + names
    if group == "mkdir" and "mkdir" in have and files.write:
        return "file_access mkdir"
    if group == "delete" and "delete" in have and files.delete:
        return "file_access delete"
    if group == "move" and "move" in have and files.write:
        return "file_access move"
    if group == "copy" and {"read", "write"} <= have and files.write:
        return "file_access read, then write"
    if group == "write" and "write" in have and files.write:
        return "file_access write"
    return "not available; that file action is switched off"


def _shown(names: tuple[str, ...], count: int, allowed: set[str]) -> list[str]:
    return [name for name in names if name not in allowed][:count]


def alternatives(programs: list[str], root: str, files: FileReach | None) -> list[str]:
    """Lines for the terminal block: habits that do not work here, and what to use."""
    allowed = {program.lower() for program in programs}
    lines = ["Not available in this terminal, and what to use instead:"]
    for group, names, count in _HABITS:
        shown = _shown(names, count, allowed)
        if not shown:
            continue
        label = ", ".join(shown)
        if group == "write":
            label = ", ".join("echo > file" if name == "echo" else name for name in shown)
        lines.append(f"- {label}: {_replacement(group, files, root)}.")
    scripts = "the project's own scripts" + (" (for example npm run build)" if "npm" in allowed else "")
    lines.append(f"- node -e, python -c, --eval: inline code is rejected. Build and test with {scripts}.")
    lines.append("- &&, ;, |, >, 2>: one program per call. Send the next command as its own call.")
    return lines


def _program(command: str) -> str:
    first = (command.strip().split() or [""])[0].strip("\"'").lower()
    first = first.replace("\\", "/").rsplit("/", 1)[-1]
    return first[:-4] if first.endswith(".exe") else first


def _example(command: str) -> str:
    flat = " ".join(command.split()).replace("`", "'")
    return flat if len(flat) <= _EXAMPLE_CHARS else flat[: _EXAMPLE_CHARS - 1] + "…"


def _syntax_kind(command: str) -> str:
    text = command.strip()
    if re.match(r"(?i)^cd\b", text):
        return "cd"
    if "&&" in text or ";" in text or "||" in text:
        return "chain"
    if "|" in text:
        return "pipe"
    if ">" in text or "<" in text:
        return "redirect"
    return "shell"


def lesson(
    command: str,
    error_key: str,
    *,
    programs: list[str],
    root: str,
    files: FileReach | None,
) -> tuple[str, str] | None:
    """``(key, line)`` for one rejected command, or None. One key per kind of mistake."""
    if error_key not in LESSON_KEYS or not command.strip():
        return None
    example = f"`{_example(command)}`"
    allowed = ", ".join(programs) or "none"
    if error_key == "tools.terminal.inlineCode":
        return "inline", (
            f"{example}: inline code (-e, -c, --eval) is rejected. Build and test with the project's own scripts; "
            "read and check files with file_access."
        )
    if error_key == "tools.terminal.outsideRoot":
        return "outside", f"{example}: a directory outside {root} is rejected; commands already run there."
    if error_key == "tools.terminal.shellSyntax":
        kind = _syntax_kind(command)
        if kind == "cd":
            return "cd", f"{example}: there is no cd; every command runs in {root}. Use paths relative to it."
        if kind == "chain":
            return "chain", f"{example}: one program per call; send the next command as its own call."
        if kind == "pipe":
            search = _replacement("search", files, root)
            return "pipe", f"{example}: pipes are rejected. Run one program; to find text use {search}."
        if kind == "redirect":
            write = _replacement("write", files, root)
            return "redirect", f"{example}: redirection is rejected; to write a file use {write}."
        return "shell", f"{example}: shell syntax is rejected. Send one program with its arguments."
    program = _program(command)
    group = _GROUP_OF.get(program)
    if group is None:
        return f"program:{program}", f"{example}: {program} is not allowed here. Allowed programs: {allowed}."
    return group, f"{example}: {program} is not allowed here. Use {_replacement(group, files, root)}."


def block(lines: list[str]) -> str:
    if not lines:
        return ""
    return _BLOCK_HEAD + "\n" + "\n".join(f"- {line}" for line in lines)


def block_for(ctrl, agent_id: str) -> str:
    """The lessons of one agent in this run, as a system prompt block ('' when none)."""
    store = getattr(ctrl, "terminal_lessons", None) or {}
    return block(list((store.get(agent_id) or {}).values()))


def note(ctrl, compiled, agent_id: str, arguments: str, body: str) -> str | None:
    """Record the lesson of a rejected terminal call. Returns its key when the block changed."""
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    error_key = str(data.get("errorKey") or "")
    if error_key not in LESSON_KEYS:
        return None
    try:
        args = json.loads(arguments or "{}")
    except ValueError:
        return None
    command = str(args.get("command") or "") if isinstance(args, dict) else ""
    from app.run.capabilities import file_reach, terminal_facts

    programs, root = terminal_facts(compiled, agent_id)
    found = lesson(command, error_key, programs=programs, root=root, files=file_reach(compiled, agent_id))
    if found is None:
        return None
    key, line = found
    store = ctrl.terminal_lessons.setdefault(agent_id, {})
    if key in store:
        # The kind is known; the newer example replaces the line, the block stays the same size.
        changed = store[key] != line
        store.pop(key)
        store[key] = line
        return key if changed else None
    store[key] = line
    while len(store) > MAX_LESSONS:
        store.pop(next(iter(store)))
    return key


def refresh_system(messages: list, old: str, new: str) -> None:
    """Put the lesson block into the system message: replace the old block or append it."""
    if not messages or messages[0].role != "system" or not new:
        return
    text = messages[0].content or ""
    if old and old in text:
        text = text.replace(old, new)
    else:
        text = text.rstrip() + "\n\n" + new
    messages[0] = messages[0].model_copy(update={"content": text})
