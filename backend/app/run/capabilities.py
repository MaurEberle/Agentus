"""Plain inventory of the tools and MCP servers wired to one node.

The model sees this in the system prompt. The tool schema alone is not enough:
callers omit `action` or name programs that were never granted.
"""

from __future__ import annotations

from app.run.compile import CompiledGraph
from app.run.graph_models import is_mcp_node
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
            blocks.append(_terminal_block(title, node.data))
        else:
            blocks.append(f"## {title}\nTool name: {kind}.")
    if not blocks:
        return ""
    head = (
        "# Connected tools, open on this turn\n"
        "Call only a tool listed here, with a native tool call. Do not invent an action, a program, "
        "or a path outside the stated root. A file_access call without action is rejected."
    )
    return head + "\n\n" + "\n\n".join(blocks)


def _blocks(compiled: CompiledGraph, owner_id: str) -> list[str]:
    by_id = {node.id: node for node in compiled.doc.nodes}
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
            blocks.append(_terminal_block(title, node.data))
        elif kind:
            blocks.append(f"## {title}\nTool name: {kind}.")
    return blocks


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
    return "\n".join(lines)


def _terminal_block(title: str, data: dict) -> str:
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
