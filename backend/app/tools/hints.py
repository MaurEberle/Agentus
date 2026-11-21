"""A short fix for the model when a built-in tool call failed.

A failed call used to return only its key (``tools.fileAccess.outsideRoot``).
The rules stood in the system prompt, far away; a weak model repeated the same
mistake dozens of times (one run: 45 paths like ``/c/dev/...``). The hint says
what to send instead, with the values of this tool node.
"""

from __future__ import annotations

from typing import Any


def _root(config: dict[str, Any]) -> str:
    return str(config.get("rootPath") or config.get("root") or "").strip()


def _file_actions(config: dict[str, Any]) -> list[str]:
    from app.tools.file_access_tool import FILE_ACTION_ORDER, _chosen_actions

    chosen = _chosen_actions(config)
    return [name for name in FILE_ACTION_ORDER if chosen is None or name in chosen]


def _programs(config: dict[str, Any]) -> list[str]:
    from app.tools.terminal_tool import _programs as granted

    return sorted(granted(config))


def _file_hint(key: str, config: dict[str, Any]) -> str | None:
    root = _root(config)
    leaf = key.rsplit(".", 1)[-1]
    if leaf in {"outsideRoot", "invalidPath"}:
        return (
            f"Paths are relative to the project root {root}. Send a path like src/App.tsx. "
            f"An absolute path must start with {root}."
        )
    if leaf == "invalidAction":
        actions = ", ".join(_file_actions(config))
        return (
            f"Every call needs an action. Allowed: {actions}. "
            'Example: {"action": "read", "path": "src/App.tsx"}.'
        )
    if leaf == "notFound":
        return "Nothing exists at this path. List or tree the folder first, then use a path from that result."
    if leaf == "notFile":
        return "This path is a folder. Use list or tree for a folder, read for a file."
    if leaf == "notDir":
        return (
            "This path is a file, not a folder. Use read for a file; "
            'to find text in it, use search with text: {"action": "search", "path": "<file>", "text": "<text>"}.'
        )
    if leaf == "invalidText":
        return "search text is one line of at most 200 characters. Send a shorter piece of the text."
    if leaf == "editMiss":
        return (
            "oldText was not found exactly. Read the file again and copy the exact lines, "
            "or write the whole file with write."
        )
    if leaf in {"disabled", "readOnly", "deleteDenied"}:
        return "This action is switched off for this tool. Do not try it again."
    return None


def _terminal_hint(key: str, config: dict[str, Any]) -> str | None:
    root = _root(config)
    leaf = key.rsplit(".", 1)[-1]
    if leaf == "shellSyntax":
        return (
            "There is no shell. Send one program with its arguments, without &&, ;, |, >, 2> or cd. "
            f"The working directory is already the project root {root}, and stdout and stderr "
            "both come back, so cd to the root, 2>&1 and a trailing | head or | tail are not needed. "
            "To find text in files, use file_access search with text instead of | grep."
        )
    if leaf == "notGranted":
        programs = ", ".join(_programs(config)) or "none"
        return (
            f"Allowed programs: {programs}. Commands like ls, pwd, cd, echo, cat, grep, findstr and find "
            "do not exist here; use the file_access tool to list and read files, and its search with text "
            "to find text in files."
        )
    if leaf == "inlineCode":
        return (
            "Inline code (-c, -e, --eval) is not allowed. Read and check files with the file_access tool; "
            "its search with text finds text in files. "
            "Build or test with the project's own scripts (for example npm run build or npm test). "
            "Do not add helper scripts to the project; if one is unavoidable, delete it when you are done."
        )
    if leaf == "outsideRoot":
        return f"A directory option must point inside the project root {root}. Leave it out; the command already runs there."
    if leaf == "timeout":
        return (
            "The command did not end in time and was stopped. Do not start servers or watch modes "
            "(npm run dev); run a build or a test command that ends."
        )
    if leaf == "notFound":
        return "This program is not installed on this computer."
    return None


def _setup_hint(key: str, config: dict[str, Any]) -> str | None:
    leaf = key.rsplit(".", 1)[-1]
    root = _root(config)
    if leaf == "rootNotDir":
        return f"The folder of this tool ({root or 'not set'}) does not exist. The tool cannot work in this run."
    if leaf == "missingRoot":
        return "This tool has no folder set. The tool cannot work in this run."
    return None


def failure_hint(kind: str, error_key: str, config: dict[str, Any] | None) -> str | None:
    cfg = config or {}
    setup = _setup_hint(error_key, cfg)
    if setup:
        return setup
    if kind == "file_access" and error_key.startswith("tools.fileAccess."):
        return _file_hint(error_key, cfg)
    if kind == "terminal" and error_key.startswith("tools.terminal."):
        return _terminal_hint(error_key, cfg)
    return None
