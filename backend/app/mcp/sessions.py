"""Lazy MCP sessions. Tests mock ``connect_transport``; the harness stays sync."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Protocol

from app.common.secrets import mask_obj
from app.db.errors import PersistError
from app.db.settings import get_mcp_server
from app.db.vault import get as vault_get
from app.mcp.models import McpToolInfo
from app.mcp.recipe_loader import get_recipe
from app.mcp.runtime_check import runtime_available
from app.mcp.sandbox import reject_app_db_dsn, resolve_args

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
        listed = self._run(self._session.list_tools(), timeout=15)
        tools = getattr(listed, "tools", listed) or []
        out: list[McpToolInfo] = []
        for tool in tools:
            schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}
            out.append(
                McpToolInfo(
                    name=str(getattr(tool, "name", "")),
                    description=getattr(tool, "description", None),
                    input_schema=schema if isinstance(schema, dict) else {},
                )
            )
        return out

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raw = self._run(self._session.call_tool(name, arguments), timeout=60)
        is_error = bool(getattr(raw, "isError", False) or (isinstance(raw, dict) and raw.get("isError")))
        return {"isError": is_error, "result": _content(raw)}

    def close(self) -> None:
        try:
            self._run(_teardown(self), timeout=3)
        except Exception:
            pass
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass


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


def _content(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw.get("result", raw)
    content = getattr(raw, "content", None)
    if not content:
        return None
    texts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            texts.append(text)
    if not texts:
        return None
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except ValueError:
            return texts[0]
    return texts


class _Live:
    def __init__(self, session: TransportSession) -> None:
        self.session = session
        self.last_used = time.monotonic()
        self.timer: threading.Timer | None = None


class McpSessions:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._live: dict[str, _Live] = {}

    def open_for(self, server_ids: list[str]) -> None:
        unique: list[str] = []
        for sid in server_ids:
            if sid not in unique:
                unique.append(sid)
        if not unique:
            return
        try:
            for sid in unique:
                self._open_one(sid)
        except Exception:
            self.close_all()
            raise

    def _open_one(self, server_id: str) -> None:
        with self._lock:
            if server_id in self._live:
                return
        row = get_mcp_server(server_id)
        if row is None:
            raise McpError("mcp.notFound")
        if not row.get("enabled"):
            raise McpError("graph.mcp.disabled")
        recipe = get_recipe(str(row.get("recipe_id") or "")) if row.get("recipe_id") else None
        root = row.get("root_path")
        needs_root = bool(recipe.needs_root) if recipe else False
        if needs_root and not root:
            raise McpError("graph.mcp.root")
        runtime = recipe.runtime if recipe else "none"
        if not runtime_available(runtime):
            raise McpError("mcp.runtime.missing")
        env, headers = _spawn_env(row, recipe)
        args = list(row.get("args") or (recipe.args if recipe else []))
        append = recipe.append_root if recipe else False
        args = resolve_args(args, root, append_root=append)
        command = row.get("command") or (recipe.command if recipe else None)
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
        live = _Live(session)
        with self._lock:
            self._live[server_id] = live
        self._arm_idle(server_id)

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
        try:
            raw = live.session.call_tool(tool_name, arguments)
        except Exception:
            return {"ok": False, "errorKey": "mcp.call.failed"}
        if raw.get("isError"):
            return {
                "ok": False,
                "errorKey": "mcp.call.failed",
                "result": mask_obj(raw.get("result")),
            }
        return {"ok": True, "result": mask_obj(raw.get("result"))}

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
