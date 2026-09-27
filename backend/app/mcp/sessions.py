"""Lazy MCP sessions. Tests mock ``connect_transport``; the harness stays sync."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Protocol

from app.common.secrets import mask_obj, mask_text
from app.db.errors import PersistError
from app.db.settings import get_mcp_server, put_mcp_server
from app.db.vault import get as vault_get
from app.mcp.models import McpToolInfo
from app.mcp.recipe_loader import get_recipe

from app.mcp.payload import coerce_tool_arguments, compact_tool_result
from app.http.errors import AppError
from app.mcp.runtime_check import resolve_stdio_command, runtime_available
from app.mcp.excel_files import annotate_excel_tools, folder_tool_result, workbook_hint
from app.mcp.sandbox import confine_tool_arguments, reject_app_db_dsn, resolve_args

IDLE_SEC = 300.0


class TransportSession(Protocol):
    def list_tools(self) -> list[McpToolInfo]: ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...

    def close(self) -> None: ...


class McpError(PersistError):
    pass


def connect_transport(
    *,
    transport: str,
    command: str | None,
    args: list[str],
    url: str | None,
    env: dict[str, str],
    cwd: str | None,
    headers: dict[str, str] | None = None,
) -> TransportSession:
    """SDK boundary. Tests replace this function."""
    return _SdkSession(
        transport=transport,
        command=command,
        args=args,
        url=url,
        env=env,
        cwd=cwd,
        headers=headers or {},
    )


class _SdkSession:
    def __init__(
        self,
        *,
        transport: str,
        command: str | None,
        args: list[str],
        url: str | None,
        env: dict[str, str],
        cwd: str | None,
        headers: dict[str, str],
    ) -> None:
        import asyncio

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._stdio_cm: Any = None
        self._http_cm: Any = None
        self._session_cm: Any = None
        self._session: Any = None
        self._run(_setup(self, transport, command, args, url, env, cwd, headers), timeout=15)

    def _run(self, coro: Any, timeout: float = 15.0) -> Any:
        import asyncio

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def list_tools(self) -> list[McpToolInfo]:
        return self._run(_list_tools_tolerant(self._session), timeout=15)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._run(_call_tool_tolerant(self._session, name, arguments), timeout=60)

    def close(self) -> None:
        try:
            self._run(_teardown(self), timeout=3)
        except Exception:
            pass
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass


def _inline_json_schema_ref(schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return schema
    defs = schema.get("$defs") or schema.get("definitions") or {}
    if not isinstance(defs, dict):
        return schema
    target = defs.get(ref.rsplit("/", 1)[-1])
    if not isinstance(target, dict):
        return schema
    merged = dict(target)
    for key, value in schema.items():
        if key != "$ref":
            merged[key] = value
    return merged


def schema_properties_empty(schema: dict[str, Any]) -> bool:
    props = schema.get("properties")
    return not isinstance(props, dict) or len(props) == 0


def repair_input_schema(schema: object) -> dict[str, Any]:
    """Older MCP servers omit JSON Schema ``type``; the Python SDK requires it.

    npm MCP 0.6.x plus Zod 4 often yields only ``$schema`` (zod-to-json-schema
    cannot convert Zod 4). Inline ``$ref`` when present; callers overlay
    recipe fallbacks when properties stay empty.
    """
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}
    out = _inline_json_schema_ref(dict(schema))
    if "type" not in out:
        out["type"] = "object"
    if out.get("type") == "object" and "properties" not in out:
        out["properties"] = {}
    return out


def github_login(token: str | None) -> str | None:
    if not token:
        return None
    try:
        import urllib.request

        request = urllib.request.Request(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "agentus-network",
            },
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            body = json.loads(response.read().decode("utf-8"))
        login = body.get("login") if isinstance(body, dict) else None
        return str(login) if login else None
    except Exception:
        return None


def annotate_github_login(tools: list[McpToolInfo], token: str | None) -> list[McpToolInfo]:
    login = github_login(token)
    if not login:
        return tools
    note = (
        f" Authenticated user is {login}. "
        f"To list that user's repositories, set query to user:{login}."
    )
    out: list[McpToolInfo] = []
    for tool in tools:
        description = tool.description or ""
        schema = dict(tool.input_schema or {})
        if tool.name == "search_repositories":
            description = (description + note).strip()
            props = dict(schema.get("properties") or {})
            query = dict(props.get("query") or {"type": "string"})
            extra = f" For the signed-in account use user:{login}."
            if extra not in str(query.get("description") or ""):
                query["description"] = (query.get("description") or "Search query") + extra
            props["query"] = query
            schema["properties"] = props
        out.append(
            McpToolInfo(name=tool.name, description=description, input_schema=schema)
        )
    return out


def apply_recipe_tool_schemas(
    tools: list[McpToolInfo], recipe: Any | None
) -> list[McpToolInfo]:
    fallbacks = dict(getattr(recipe, "tool_schemas", None) or {})
    out: list[McpToolInfo] = []
    for tool in tools:
        schema = repair_input_schema(tool.input_schema)
        if schema_properties_empty(schema):
            overlay = fallbacks.get(tool.name)
            if isinstance(overlay, dict):
                schema = repair_input_schema(overlay)
        out.append(
            McpToolInfo(
                name=tool.name,
                description=tool.description,
                input_schema=schema,
            )
        )
    return out


def tools_from_list_payload(raw: object) -> list[McpToolInfo]:
    items = raw.get("tools") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        items = getattr(raw, "tools", None)
    if not isinstance(items, list):
        return []
    out: list[McpToolInfo] = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or "")
            if not name:
                continue
            schema = item.get("inputSchema") or item.get("input_schema") or {}
            out.append(
                McpToolInfo(
                    name=name,
                    description=item.get("description"),
                    input_schema=repair_input_schema(schema),
                )
            )
            continue
        name = str(getattr(item, "name", "") or "")
        if not name:
            continue
        schema = getattr(item, "inputSchema", None) or getattr(item, "input_schema", None) or {}
        out.append(
            McpToolInfo(
                name=name,
                description=getattr(item, "description", None),
                input_schema=repair_input_schema(schema),
            )
        )
    return out


def _output_schema_from_item(item: object) -> dict[str, Any] | None:
    if isinstance(item, dict):
        schema = item.get("outputSchema") or item.get("output_schema")
    else:
        schema = getattr(item, "outputSchema", None) or getattr(item, "output_schema", None)
    if isinstance(schema, dict) and schema.get("type"):
        return schema
    return None


def seed_tool_output_cache(
    session: Any, tools: list[McpToolInfo], raw_items: object = None
) -> None:
    """Fill ClientSession._tool_output_schemas so call_tool does not re-list.

    MCP SDK 2.x re-runs tools/list after a successful tools/call when the
    cache is empty. Older servers (GitHub 0.6.2) omit inputSchema.type, so
    that re-list raises ValidationError and the tool result is discarded.
    """
    cache = getattr(session, "_tool_output_schemas", None)
    if not isinstance(cache, dict):
        return
    raw_by_name: dict[str, object] = {}
    if isinstance(raw_items, list):
        for item in raw_items:
            name = None
            if isinstance(item, dict):
                name = item.get("name")
            else:
                name = getattr(item, "name", None)
            if name:
                raw_by_name[str(name)] = item
    for tool in tools:
        if tool.name in cache:
            continue
        cache[tool.name] = _output_schema_from_item(raw_by_name.get(tool.name))


async def _list_tools_tolerant(session: Any) -> list[McpToolInfo]:
    from pydantic import ValidationError

    raw_items: object = None
    try:
        listed = await session.list_tools()
        tools = tools_from_list_payload(listed)
        raw_items = getattr(listed, "tools", None)
    except ValidationError:
        dispatcher = getattr(session, "_dispatcher", None)
        if dispatcher is None:
            raise
        raw = await dispatcher.send_raw_request("tools/list", None)
        tools = tools_from_list_payload(raw)
        raw_items = raw.get("tools") if isinstance(raw, dict) else None
    seed_tool_output_cache(session, tools, raw_items)
    return tools


def call_result_from_payload(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        is_error = bool(raw.get("isError") or raw.get("is_error"))
        return {"isError": is_error, "result": _content(raw)}
    is_error = bool(getattr(raw, "isError", False) or getattr(raw, "is_error", False))
    return {"isError": is_error, "result": _content(raw)}


async def _call_tool_tolerant(
    session: Any, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Call via raw JSON-RPC so old servers are not re-validated as ListToolsResult."""
    dispatcher = getattr(session, "_dispatcher", None)
    if dispatcher is not None:
        payload = await dispatcher.send_raw_request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        return call_result_from_payload(payload)
    raw = await session.call_tool(name, arguments)
    return call_result_from_payload(raw)


async def _setup(
    holder: _SdkSession,
    transport: str,
    command: str | None,
    args: list[str],
    url: str | None,
    env: dict[str, str],
    cwd: str | None,
    headers: dict[str, str],
) -> None:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    from mcp import StdioServerParameters

    if transport == "http":
        if not url:
            raise McpError("mcp.ping.failed")
        try:
            from mcp.client.streamable_http import streamablehttp_client as http_client
        except ImportError:
            from mcp.client.sse import sse_client as http_client  # type: ignore[no-redef]
        holder._http_cm = http_client(url, headers=headers or None)
        read, write = (await holder._http_cm.__aenter__())[:2]
    else:
        params = StdioServerParameters(
            command=command or "",
            args=args,
            env=env,
            cwd=cwd,
        )
        holder._stdio_cm = stdio_client(params)
        read, write = await holder._stdio_cm.__aenter__()
    holder._session_cm = ClientSession(read, write)
    holder._session = await holder._session_cm.__aenter__()
    await holder._session.initialize()


async def _teardown(holder: _SdkSession) -> None:
    for cm in (holder._session_cm, holder._stdio_cm, holder._http_cm):
        if cm is None:
            continue
        try:
            await cm.__aexit__(None, None, None)
        except Exception:
            pass


def _content_blocks(raw: Any) -> Any:
    if isinstance(raw, dict):
        if "content" in raw:
            return raw.get("content")
        return None
    return getattr(raw, "content", None)


def _structured(raw: Any) -> Any:
    if isinstance(raw, dict):
        if "structuredContent" in raw:
            return raw.get("structuredContent")
        if "result" in raw and "content" not in raw:
            return raw.get("result")
        return None
    return getattr(raw, "structured_content", None) or getattr(raw, "structuredContent", None)


def _texts_from_blocks(content: Any) -> list[str]:
    texts: list[str] = []
    if not content:
        return texts
    items = content if isinstance(content, list) else [content]
    for item in items:
        if isinstance(item, dict):
            text = item.get("text")
        else:
            text = getattr(item, "text", None)
        if isinstance(text, str):
            texts.append(text)
    return texts


def _content(raw: Any) -> Any:
    texts = _texts_from_blocks(_content_blocks(raw))
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except ValueError:
            return texts[0]
    if len(texts) > 1:
        return texts
    structured = _structured(raw)
    if structured is not None:
        return structured
    if isinstance(raw, dict) and "result" in raw:
        return raw.get("result")
    return None


_FS_PATH_TOOLS = frozenset(
    {
        "read_file",
        "read_text_file",
        "read_media_file",
        "write_file",
        "edit_file",
        "create_directory",
        "list_directory",
        "list_directory_with_sizes",
        "directory_tree",
        "search_files",
        "get_file_info",
    }
)


def default_filesystem_arguments(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    args = dict(arguments or {})
    if name in _FS_PATH_TOOLS and not str(args.get("path") or "").strip():
        args["path"] = "."
    return args


class _Live:
    def __init__(
        self,
        session: TransportSession,
        tools: list[McpToolInfo] | None = None,
        root: str | None = None,
        recipe_id: str | None = None,
    ) -> None:
        self.session = session
        self.root = root
        self.recipe_id = recipe_id
        self.tools = list(tools or [])
        self.last_used = time.monotonic()
        self.timer: threading.Timer | None = None


class McpSessions:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._live: dict[str, _Live] = {}

    def open_for(
        self,
        server_ids: list[str],
        credential_overrides: dict[str, str] | None = None,
        root_overrides: dict[str, str] | None = None,
    ) -> None:
        unique: list[str] = []
        for sid in server_ids:
            if sid not in unique:
                unique.append(sid)
        if not unique:
            return
        overrides = credential_overrides or {}
        roots = root_overrides or {}
        try:
            for sid in unique:
                self._open_one(sid, overrides.get(sid), roots.get(sid))
        except Exception:
            self.close_all()
            raise

    def _open_one(
        self,
        server_id: str,
        credential_id: str | None = None,
        root_override: str | None = None,
    ) -> None:
        with self._lock:
            if server_id in self._live:
                return
        stored = get_mcp_server(server_id)
        if stored is None:
            raise McpError("mcp.notFound")
        row = dict(stored)
        if not row.get("enabled"):
            raise McpError("graph.mcp.disabled")
        if credential_id:
            row["credential_ids"] = [credential_id]
        recipe = get_recipe(str(row.get("recipe_id") or "")) if row.get("recipe_id") else None
        root = str(root_override or row.get("root_path") or "").strip() or None
        needs_root = bool(recipe.needs_root) if recipe else False
        if needs_root and not root:
            raise McpError("graph.mcp.root")
        if root:
            from pathlib import Path

            try:
                if not Path(root).expanduser().resolve().is_dir():
                    raise McpError("mcp.root.invalid")
            except (OSError, RuntimeError) as exc:
                raise McpError("mcp.root.invalid") from exc
        runtime = recipe.runtime if recipe else "none"
        if not runtime_available(runtime):
            raise McpError("mcp.runtime.missing")
        env, headers = _spawn_env(row, recipe)
        if recipe and recipe.id == "excel":
            env.setdefault("EXCEL_MCP_PAGING_CELLS_LIMIT", "4000")
        if recipe:
            args = list(recipe.args)
            command = recipe.command
        else:
            args = list(row.get("args") or [])
            command = row.get("command")
        append = recipe.append_root if recipe else False
        args = resolve_args(args, root, append_root=append)
        command, args = resolve_stdio_command(command, args, runtime)
        url = row.get("url") or (recipe.url if recipe else None)
        cwd = root if root else None
        session = connect_transport(
            transport=str(row.get("transport") or "stdio"),
            command=command,
            args=args,
            url=url,
            env=env,
            cwd=cwd,
            headers=headers,
        )
        tools = apply_recipe_tool_schemas(session.list_tools(), recipe)
        if recipe and recipe.id == "github":
            tools = annotate_github_login(tools, env.get("GITHUB_PERSONAL_ACCESS_TOKEN"))
        if recipe and recipe.id == "excel":
            tools = annotate_excel_tools(tools, root)
        stored["status"] = "ok"
        stored["cached_tools"] = [
            {
                "name": item.name,
                "description": item.description,
                "input_schema": item.input_schema,
            }
            for item in tools
        ]
        put_mcp_server(server_id, stored)
        live = _Live(session, tools, root=root, recipe_id=recipe.id if recipe else None)
        with self._lock:
            self._live[server_id] = live
        self._arm_idle(server_id)

    def listed_tools(self, server_id: str) -> list[McpToolInfo]:
        with self._lock:
            live = self._live.get(server_id)
            if live is not None:
                return list(live.tools)
        row = get_mcp_server(server_id) or {}
        cached = row.get("cached_tools") or []
        out: list[McpToolInfo] = []
        if isinstance(cached, list):
            for item in cached:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                schema = item.get("input_schema") or item.get("inputSchema") or {}
                out.append(
                    McpToolInfo(
                        name=str(item["name"]),
                        description=item.get("description"),
                        input_schema=schema if isinstance(schema, dict) else {},
                    )
                )
        return out

    def close_all(self) -> None:
        with self._lock:
            items = list(self._live.items())
            self._live.clear()
        for _sid, live in items:
            if live.timer:
                live.timer.cancel()
            try:
                live.session.close()
            except Exception:
                pass

    def call(self, server_id: str, tool_name: str, arguments: dict) -> dict:
        with self._lock:
            live = self._live.get(server_id)
        if live is None:
            return {"ok": False, "errorKey": "mcp.session.closed"}
        live.last_used = time.monotonic()
        self._arm_idle(server_id)
        args = coerce_tool_arguments(arguments) if isinstance(arguments, dict) else arguments
        if not isinstance(args, dict):
            args = {}
        if live.recipe_id == "filesystem":
            args = default_filesystem_arguments(tool_name, args)
        if live.root:
            try:
                args = confine_tool_arguments(args, live.root)
            except AppError as exc:
                return {"ok": False, "errorKey": exc.message_key}
        if live.recipe_id == "excel":
            listing = folder_tool_result(args, live.root)
            if listing:
                return {"ok": True, "result": listing}
        try:
            raw = live.session.call_tool(tool_name, args)
        except Exception as exc:
            return {
                "ok": False,
                "errorKey": "mcp.call.failed",
                "error": mask_text(str(exc)[:400]),
            }
        if raw.get("isError"):
            payload = {
                "ok": False,
                "errorKey": "mcp.call.failed",
                "result": mask_obj(raw.get("result")),
            }
            if live.recipe_id == "excel" and live.root:
                payload["error"] = workbook_hint(live.root)
            return payload
        return {"ok": True, "result": mask_obj(compact_tool_result(raw.get("result")))}

    def is_enabled(self, server_id: str) -> bool:
        row = get_mcp_server(server_id)
        return bool(row and row.get("enabled"))

    def root_path(self, server_id: str) -> str | None:
        row = get_mcp_server(server_id)
        if not row:
            return None
        value = row.get("root_path")
        return str(value) if value else None

    def _arm_idle(self, server_id: str) -> None:
        with self._lock:
            live = self._live.get(server_id)
            if live is None:
                return
            if live.timer:
                live.timer.cancel()
            timer = threading.Timer(IDLE_SEC, self._idle_close, args=(server_id,))
            timer.daemon = True
            live.timer = timer
            timer.start()

    def _idle_close(self, server_id: str) -> None:
        with self._lock:
            live = self._live.pop(server_id, None)
        if live is None:
            return
        if live.timer:
            live.timer.cancel()
        try:
            live.session.close()
        except Exception:
            pass


def _spawn_env(row: dict[str, Any], recipe: Any) -> tuple[dict[str, str], dict[str, str]]:
    env = os.environ.copy()
    headers: dict[str, str] = {}
    kinds = list(recipe.credential_kinds) if recipe else []
    env_map = dict(recipe.env_from_kind) if recipe else {}
    ids = list(row.get("credential_ids") or [])
    for index, kind in enumerate(kinds):
        if index >= len(ids):
            break
        secret = vault_get(ids[index])
        if kind == "postgres":
            reject_app_db_dsn(secret)
        env_name = env_map.get(kind)
        if secret and env_name:
            env[env_name] = secret
        if secret and not env_name and kind in {"token", "linear", "xai"}:
            headers["Authorization"] = f"Bearer {secret}"
        elif secret and recipe and recipe.transport == "http" and index == 0 and not env_name:
            headers["Authorization"] = f"Bearer {secret}"
    return env, headers


SESSIONS = McpSessions()
