"""Plain inventory of the tools and MCP servers wired to one node.

The model sees this in the system prompt. The tool schema alone is not enough:
callers omit `action` or name programs that were never granted.
"""

from __future__ import annotations

from app.run.compile import CompiledGraph
from app.run.graph_models import is_mcp_node
from app.run.terminal_lessons import FileReach, alternatives
from app.tools.file_access_tool import FILE_ACTION_ORDER

_FILE_WRITES = ("write", "mkdir", "edit", "move")
_FILE_DELETES = ("delete",)


def capability_text(
    compiled: CompiledGraph, owner_id: str, *, available: bool, read_only: bool = False
) -> str:
    blocks = _blocks(compiled, owner_id)
    if not blocks:
        return (
            "# Connected tools\n"
            "No tools and no MCP servers are connected. Do not call a tool."
        )
    if available and read_only:
        head = (
            "Available on this turn for reading and checking: file list, read, tree, stat and search, "
            "the terminal, web search. Changing files, zip, HTTP and MCP tools open after an agent call "
            "failed or during a takeover. Call only an available tool, with a tool call."
        )
    elif available:
        head = "Available on this turn. Call only a name listed here, with a tool call."
    else:
        head = (
            "Connected, but not available on this turn. Do not call a tool. "
            "Call an agent. These tools are offered only after an agent fails or during file takeover."
        )
    rules = (
        "Do not invent an action, a program, or a path outside the stated root. "
        "A file_access call without action is rejected."
    )
    return "# Connected tools\n" + head + "\n" + rules + "\n\n" + "\n\n".join(blocks)


def orchestrator_capabilities(compiled: CompiledGraph, owner_id: str, offered: list[dict]) -> str:
    """Connected tools of the orchestrator as far as they are open on this turn.

    The agent text listed every action of the node ("Write: allowed") while the
    orchestrator could not write; the model then tried to write (Dev Team run,
    2026-11-17). Here a tool that is not offered is not mentioned, and the file
    block names only the actions in the offered schema.
    """
    from app.run.mcp_bridge import map_openai_tool_name

    names: set[str] = set()
    file_actions: list[str] | None = None
    servers: set[str] = set()
    for item in offered:
        function = item.get("function") or {}
        name = str(function.get("name") or "")
        if not name:
            continue
        names.add(name)
        mapped = map_openai_tool_name(name)
        if mapped:
            servers.add(mapped[0])
        if name == "file_access":
            props = (function.get("parameters") or {}).get("properties") or {}
            enum = (props.get("action") or {}).get("enum")
            if isinstance(enum, list):
                file_actions = [str(action) for action in enum]
    if not names:
        return ""
    by_id = {node.id: node for node in compiled.doc.nodes}
    blocks: list[str] = []
    for edge in compiled.doc.edges:
        if edge.target != owner_id or edge.target_handle != "tool":
            continue
        node = by_id.get(edge.source)
        if node is None:
            continue
        if is_mcp_node(node):
            if str(node.data.get("mcpServerId") or "") in servers:
                blocks.append(_mcp_block(node.data))
            continue
        kind = str(node.data.get("kind") or "")
        if kind not in names:
            continue
        title = str(node.data.get("displayName") or kind or node.id)
        if kind == "file_access":
            blocks.append(_file_block(title, node.data, only=file_actions))
        elif kind == "terminal":
            reach = file_reach(compiled, owner_id, only=file_actions) if file_actions is not None else None
            blocks.append(_terminal_block(title, node.data, reach))
        else:
            blocks.append(_simple_block(title, kind))
    if not blocks:
        return ""
    head = (
        "# Connected tools, open on this turn\n"
        "Call only a tool listed here, with a native tool call. Do not invent an action, a program, "
        "or a path outside the stated root. A file_access call without action is rejected."
    )
    return head + "\n\n" + "\n\n".join(blocks)


# What each simple tool is for, in the orchestrator overview and the agent roster.
_KIND_USE = {
    "web_search": "searches the web and returns titles, links and snippets",
    "http": "fetches an http or https URL",
    "zip": "lists or extracts .zip files",
    "datetime": "tells the current time and does date arithmetic",
    "calculator": "evaluates arithmetic",
}
_KIND_LABEL = {
    "web_search": "web search",
    "http": "HTTP",
    "zip": "zip",
    "datetime": "date and time",
    "calculator": "calculator",
}
_OPENS_LATER = "opens only after an agent call failed or during a takeover"


def _tool_nodes(compiled: CompiledGraph, owner_id: str) -> list:
    by_id = {node.id: node for node in compiled.doc.nodes}
    nodes = []
    for edge in compiled.doc.edges:
        if edge.target != owner_id or edge.target_handle != "tool":
            continue
        node = by_id.get(edge.source)
        if node is not None:
            nodes.append(node)
    return nodes


def _file_actions_of(data: dict) -> list[str]:
    chosen = data.get("fileActions")
    if isinstance(chosen, list) and chosen:
        return [name for name in FILE_ACTION_ORDER if name in {str(item) for item in chosen}]
    return list(FILE_ACTION_ORDER)


def _file_changes_allowed(data: dict) -> bool:
    actions = _file_actions_of(data)
    writes = data.get("allowWrite") is not False and any(name in _FILE_WRITES for name in actions)
    deletes = data.get("allowDelete") is not False and "delete" in actions
    return writes or deletes


def _programs_of(data: dict) -> list[str]:
    from app.tools.terminal_tool import DEFAULT_PROGRAMS

    raw = data.get("terminalPrograms")
    if not (isinstance(raw, list) and raw):
        return list(DEFAULT_PROGRAMS)
    programs = []
    for item in raw:
        name = str(item).strip()
        if name.lower().endswith(".exe"):
            name = name[:-4]
        if name:
            programs.append(name)
    return programs


def _unrestricted(data: dict) -> bool:
    return str(data.get("terminalMode") or "restricted").strip().lower() == "unrestricted"


def _root_of(data: dict) -> str:
    return str(data.get("rootPath") or "").strip() or "(no root)"


def _mcp_title(data: dict) -> tuple[str, str]:
    server_id = str(data.get("mcpServerId") or "").strip()
    server_name, _root = _server_facts(server_id)
    title = str(data.get("displayName") or "").strip() or server_name or server_id or "MCP"
    return title, server_id


def _mcp_tool_names(data: dict, server_id: str) -> list[str]:
    allow = data.get("mcpToolNames")
    if isinstance(allow, list) and allow:
        return [str(item) for item in allow]
    return [name for name, _ in _live_tools(server_id)]


def file_reach(compiled: CompiledGraph, owner_id: str, only: list[str] | None = None) -> FileReach | None:
    """The file actions of the first file_access node wired to ``owner_id``; None without one."""
    for node in _tool_nodes(compiled, owner_id):
        if is_mcp_node(node) or str(node.data.get("kind") or "") != "file_access":
            continue
        actions = _file_actions_of(node.data)
        if only is not None:
            actions = [name for name in actions if name in set(only)]
        return FileReach(
            actions=actions,
            write=node.data.get("allowWrite") is not False and any(name in _FILE_WRITES for name in actions),
            delete=node.data.get("allowDelete") is not False and "delete" in actions,
        )
    return None


def terminal_facts(compiled: CompiledGraph, owner_id: str) -> tuple[list[str], str]:
    """Allowed programs and working folder of the terminal wired to ``owner_id``."""
    for node in _tool_nodes(compiled, owner_id):
        if not is_mcp_node(node) and str(node.data.get("kind") or "") == "terminal":
            return _programs_of(node.data), _root_of(node.data)
    return [], "(no root)"


def tool_summary(compiled: CompiledGraph, owner_id: str) -> str:
    """The tools wired to one node in a few words, for the orchestrator's roster.

    The orchestrator could not tell which agent can read files; it planned to read
    them itself instead (Coder_Team run, 2026-11-20).
    """
    parts: list[str] = []
    for node in _tool_nodes(compiled, owner_id):
        data = node.data
        if is_mcp_node(node):
            title, _server = _mcp_title(data)
            parts.append(f"MCP server {title}")
            continue
        kind = str(data.get("kind") or "")
        if kind == "file_access":
            mode = "read and change" if _file_changes_allowed(data) else "read only"
            parts.append(f"file access ({mode}) in {_root_of(data)}")
        elif kind == "terminal":
            if _unrestricted(data):
                parts.append("terminal (PowerShell)")
            else:
                parts.append("terminal (" + ", ".join(_programs_of(data)) + ")")
        elif kind:
            parts.append(_KIND_LABEL.get(kind, kind))
    return ", ".join(parts) if parts else "none"


def orchestrator_tool_overview(
    compiled: CompiledGraph, owner_id: str, open_names: list[str], *, write_open: bool = False
) -> str:
    """Every tool wired to the orchestrator: what it does and whether it is open on this turn.

    The prompt used to mention only the tools open on a turn. Without file access the
    orchestrator still planned to "check the files myself", eight decisions in a row, and
    the run ended stuck (Coder_Team run, 2026-11-20). Now it reads what it can reach.
    ``write_open``: after a failed agent call or in a takeover it may change files now.
    """
    from app.run.mcp_bridge import map_openai_tool_name

    opened = set(open_names)
    open_servers = {mapped[0] for mapped in (map_openai_tool_name(name) for name in open_names) if mapped}
    files: list[str] = []
    others: list[str] = []
    for node in _tool_nodes(compiled, owner_id):
        data = node.data
        if is_mcp_node(node):
            title, server_id = _mcp_title(data)
            names = _mcp_tool_names(data, server_id)
            tools = (", ".join(names[:6]) + (", ..." if len(names) > 6 else "")) if names else "its published tools"
            status = "open now" if server_id in open_servers else _OPENS_LATER
            others.append(f"- {title} (MCP server): {tools}; {status}.")
            continue
        kind = str(data.get("kind") or "")
        title = str(data.get("displayName") or kind or node.id)
        if kind == "file_access":
            root = _root_of(data)
            if "file_access" not in opened:
                files.append(f"Files: your file access in {root} is not open on this turn.")
            elif not _file_changes_allowed(data):
                files.append(f"Files: you can read files in {root} yourself; changing them is switched off.")
            elif write_open:
                files.append(
                    f"Files: you can read and change files in {root} on this turn "
                    "(search with text finds text inside files)."
                )
            else:
                files.append(
                    f"Files: you can read files in {root} yourself (search with text finds text inside files); "
                    f"changing them {_OPENS_LATER}."
                )
            continue
        if kind == "terminal":
            use = (
                f"runs one PowerShell command in {_root_of(data)}"
                if _unrestricted(data)
                else f"runs one allowed program ({', '.join(_programs_of(data))}) in {_root_of(data)}"
            )
        elif kind:
            use = _KIND_USE.get(kind, "a connected tool")
        else:
            continue
        status = "open now" if kind in opened else _OPENS_LATER
        others.append(f"- {title} ({kind}): {use}; {status}.")
    if not files:
        files.append(
            "Files: you have no file access. To read or check a file, call an agent with file access "
            "(see tools in the roster) and say what it should look for."
        )
    lines = files
    if others:
        lines = lines + ["Other tools connected to you:"] + others
    return "\n".join(lines)


def _blocks(compiled: CompiledGraph, owner_id: str) -> list[str]:
    by_id = {node.id: node for node in compiled.doc.nodes}
    files = file_reach(compiled, owner_id)
    blocks: list[str] = []
    for edge in compiled.doc.edges:
        if edge.target != owner_id or edge.target_handle != "tool":
            continue
        node = by_id.get(edge.source)
        if node is None:
            continue
        if is_mcp_node(node):
            blocks.append(_mcp_block(node.data))
            continue
        kind = str(node.data.get("kind") or "")
        title = str(node.data.get("displayName") or kind or node.id)
        if kind == "file_access":
            blocks.append(_file_block(title, node.data))
        elif kind == "terminal":
            blocks.append(_terminal_block(title, node.data, files))
        elif kind:
            blocks.append(_simple_block(title, kind))
    return blocks


def _simple_block(title: str, kind: str) -> str:
    use = _KIND_USE.get(kind)
    return f"## {title}\nTool name: {kind}." + (f"\nUse: {use}." if use else "")


def _file_block(title: str, data: dict, *, only: list[str] | None = None) -> str:
    root = str(data.get("rootPath") or "").strip() or "(no root)"
    chosen = data.get("fileActions")
    if isinstance(chosen, list) and chosen:
        actions = [name for name in FILE_ACTION_ORDER if name in {str(item) for item in chosen}]
    else:
        actions = list(FILE_ACTION_ORDER)
    if only is not None:
        actions = [name for name in actions if name in set(only)]
    allow_write = data.get("allowWrite")
    allow_delete = data.get("allowDelete")
    write_note = "allowed" if allow_write is not False else "denied"
    delete_note = "allowed" if allow_delete is not False else "denied"
    writes = [name for name in _FILE_WRITES if name in actions]
    lines = [
        f"## {title}",
        "Tool name: file_access.",
        f"Root: {root}.",
        "Paths are relative to that root, or '.' for the root. Absolute paths and paths outside the root are rejected.",
        f"Actions: {', '.join(actions)}.",
    ]
    # A write or delete line only where those actions are offered.
    if writes or only is None:
        lines.append(f"Write ({', '.join(writes)}): {write_note}.")
    if "delete" in actions or only is None:
        lines.append(f"Delete: {delete_note}.")
    lines.append('Call shape: {"action":"<one listed action>","path":"<relative path>"}.')
    if "read" in actions:
        # H6: a file larger than one result is paged, not cut off.
        lines.append(
            "read returns one page of a file. When the result has nextOffset, more lines follow: "
            "read again with offset set to nextOffset."
        )
    if "search" in actions:
        lines.append(
            "search with text finds text inside a file or the files of a folder, like grep: "
            '{"action":"search","path":"src","text":"language-card","pattern":"*.scss"}. '
            "search with only pattern finds file names."
        )
    return "\n".join(lines)


def _terminal_block(title: str, data: dict, files: FileReach | None = None) -> str:
    from app.tools.terminal_tool import DEFAULT_PROGRAMS

    root = str(data.get("rootPath") or "").strip() or "(no root)"
    unrestricted = str(data.get("terminalMode") or "restricted").strip().lower() == "unrestricted"
    lines = [
        f"## {title}",
        "Tool name: terminal.",
        f"Working directory: {root}.",
    ]
    if unrestricted:
        lines.append(
            "Mode: unrestricted. One PowerShell command. No elevation and no interactive input."
        )
    else:
        raw = data.get("terminalPrograms")
        if isinstance(raw, list) and raw:
            programs = []
            for item in raw:
                name = str(item).strip()
                if name.lower().endswith(".exe"):
                    name = name[:-4]
                if name:
                    programs.append(name)
        else:
            programs = list(DEFAULT_PROGRAMS)
        lines.append(
            "Mode: restricted. One program from this list, plus its arguments. "
            "Pipes, redirection, and other shell syntax are rejected."
        )
        lines.append("Programs: " + ", ".join(programs) + ".")
        lines.append("A program that is not in that list is rejected.")
        # Before any mistake: what to use instead of the usual shell habits (Coder_Team run, 2026-11-20).
        lines.extend(alternatives(programs, root, files))
    return "\n".join(lines)


def _mcp_block(data: dict) -> str:
    server_id = str(data.get("mcpServerId") or "").strip()
    title = str(data.get("displayName") or "").strip()
    server_name, root = _server_facts(server_id)
    if not title:
        title = server_name or server_id or "MCP"
    root = str(data.get("rootPath") or root or "").strip()
    allow = data.get("mcpToolNames")
    allowed = [str(item) for item in allow] if isinstance(allow, list) else None
    tools = _live_tools(server_id)
    if allowed is not None:
        tools = [item for item in tools if item[0] in set(allowed)]
        if not tools:
            tools = [(name, "") for name in allowed]
    lines = [f"## {title}", "Kind: MCP server."]
    if server_name and server_name != title:
        lines.append(f"Server: {server_name}.")
    if server_id:
        lines.append(f"Server id: {server_id}.")
    if root:
        lines.append(f"Root: {root}. Paths outside this root are rejected.")
    if not tools:
        lines.append("No tools are published by this server right now.")
        return "\n".join(lines)
    lines.append("Tools:")
    for name, description in tools:
        brief = " ".join(description.split())
        if len(brief) > 180:
            brief = brief[:177] + "..."
        lines.append(f"- {name}" + (f": {brief}" if brief else ""))
    return "\n".join(lines)


def _server_facts(server_id: str) -> tuple[str, str]:
    if not server_id:
        return "", ""
    try:
        from app.db.settings import get_mcp_server

        row = get_mcp_server(server_id)
    except Exception:
        return "", ""
    if not isinstance(row, dict):
        return "", ""
    # N1: server rows store snake_case (``root_path``); rootPath is the API alias.
    return str(row.get("name") or ""), str(row.get("root_path") or row.get("rootPath") or "")


def _live_tools(server_id: str) -> list[tuple[str, str]]:
    if not server_id:
        return []
    try:
        from app.run.turn_runtime import get_mcp

        bridge = get_mcp()
        if bridge is None:
            return []
        infos = bridge.listed_tools(server_id)
    except Exception:
        return []
    out: list[tuple[str, str]] = []
    for info in infos:
        name = str(getattr(info, "name", "") or "")
        if not name:
            continue
        out.append((name, str(getattr(info, "description", "") or "")))
    return out
