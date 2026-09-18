from __future__ import annotations

import uuid
from typing import Any

from app.db.engine import get_bootstrap
from app.db.paths import local_app_data
from app.db.settings import (
    delete_mcp_server,
    get_mcp_server,
    list_mcp_servers,
    put_mcp_server,
)
from app.http.errors import AppError
from app.mcp.models import (
    McpRecipe,
    McpServerCreate,
    McpServerListItem,
    McpServerPatch,
    McpServerStatus,
    McpToolInfo,
)
from app.mcp.recipe_loader import RecipeRecord, get_recipe, load_recipes
from app.mcp.runtime_check import runtime_available
from app.mcp.sandbox import validate_root_path
from app.mcp import sessions as mcp_sessions
from app.mcp.sandbox import resolve_args


def list_recipes() -> list[McpRecipe]:
    return [
        McpRecipe(
            id=item.id,
            title_key=item.title_key,
            transport=item.transport,  # type: ignore[arg-type]
            credential_kinds=item.credential_kinds,
            needs_root=item.needs_root,
        )
        for item in load_recipes()
    ]


def _item(row: dict[str, Any]) -> McpServerListItem:
    return McpServerListItem(
        id=str(row["id"]),
        recipe_id=row.get("recipe_id"),
        name=str(row.get("name") or row["id"]),
        transport=row.get("transport") or "stdio",
        enabled=bool(row.get("enabled")),
        status=row.get("status") or "unknown",
        credential_ids=row.get("credential_ids"),
        root_path=row.get("root_path"),
    )


def list_servers() -> list[McpServerListItem]:
    return [_item(row) for row in list_mcp_servers()]


def _require(server_id: str) -> dict[str, Any]:
    row = get_mcp_server(server_id)
    if row is None:
        raise AppError("mcp.notFound", status_code=404)
    return row


def _check_root(recipe: RecipeRecord | None, root_path: str | None, enabled: bool) -> None:
    if not enabled:
        return
    needs = bool(recipe and recipe.needs_root)
    if needs and not root_path:
        raise AppError("mcp.root.required", status_code=400)
    if needs and root_path:
        bootstrap = get_bootstrap()
        validate_root_path(
            root_path, data_dir=bootstrap.data_dir, app_home=local_app_data()
        )


def _save(payload: dict[str, Any]) -> McpServerListItem:
    put_mcp_server(payload["id"], payload)
    return _item(payload)


def create_server(body: McpServerCreate) -> McpServerListItem:
    server_id = str(uuid.uuid4())
    if body.recipe_id:
        recipe = get_recipe(body.recipe_id)
        if recipe is None:
            raise AppError("mcp.notFound", status_code=404)
        kinds = recipe.credential_kinds
        creds = list(body.credential_ids or [])[: len(kinds)] if kinds else list(body.credential_ids or [])
        enabled = bool(body.enabled)
        _check_root(recipe, body.root_path, enabled)
        payload = {
            "id": server_id,
            "recipe_id": recipe.id,
            "name": (body.name or recipe.id).strip() or recipe.id,
            "transport": recipe.transport,
            "enabled": enabled,
            "command": recipe.command,
            "args": list(recipe.args),
            "url": recipe.url,
            "credential_ids": creds,
            "root_path": body.root_path,
            "custom": False,
            "status": "unknown",
            "cached_tools": None,
        }
        return _save(payload)
    if not body.transport or not (body.command or body.url):
        raise AppError("mcp.custom.invalid", status_code=400)
    enabled = bool(body.enabled)
    payload = {
        "id": server_id,
        "recipe_id": None,
        "name": (body.name or "custom").strip() or "custom",
        "transport": body.transport,
        "enabled": enabled,
        "command": body.command,
        "args": list(body.args or []),
        "url": body.url,
        "credential_ids": list(body.credential_ids or []),
        "root_path": body.root_path,
        "custom": True,
        "status": "unknown",
        "cached_tools": None,
    }
    return _save(payload)


def patch_server(server_id: str, body: McpServerPatch) -> McpServerListItem:
    row = dict(_require(server_id))
    recipe = get_recipe(str(row.get("recipe_id") or "")) if row.get("recipe_id") else None
    if body.name is not None:
        row["name"] = body.name.strip() or row["name"]
    if body.credential_ids is not None:
        kinds = recipe.credential_kinds if recipe else []
        row["credential_ids"] = (
            list(body.credential_ids)[: len(kinds)] if kinds else list(body.credential_ids)
        )
    if body.root_path is not None:
        row["root_path"] = body.root_path
    if body.command is not None:
        row["command"] = body.command
    if body.args is not None:
        row["args"] = list(body.args)
    if body.url is not None:
        row["url"] = body.url
    if body.transport is not None:
        row["transport"] = body.transport
    enabled = row.get("enabled", False) if body.enabled is None else body.enabled
    row["enabled"] = enabled
    _check_root(recipe, row.get("root_path"), bool(enabled))
    return _save(row)


def set_enabled(server_id: str, enabled: bool) -> McpServerListItem:
    return patch_server(server_id, McpServerPatch(enabled=enabled))


def delete_server(server_id: str) -> None:
    _require(server_id)
    delete_mcp_server(server_id)


def ping_server(server_id: str) -> tuple[McpServerStatus, str | None]:
    row = dict(_require(server_id))
    recipe = get_recipe(str(row.get("recipe_id") or "")) if row.get("recipe_id") else None
    runtime = recipe.runtime if recipe else "none"
    if not runtime_available(runtime):
        row["status"] = "runtime_missing"
        _save(row)
        return "runtime_missing", "mcp.runtime.missing"
    if (row.get("transport") == "http" or (recipe and recipe.transport == "http")) and not (
        row.get("url") or (recipe.url if recipe else None)
    ):
        row["status"] = "error"
        _save(row)
        return "error", "mcp.ping.failed"
    try:
        env, headers = mcp_sessions._spawn_env(row, recipe)
        root = row.get("root_path")
        args = resolve_args(
            list(row.get("args") or (recipe.args if recipe else [])),
            root,
            append_root=recipe.append_root if recipe else False,
        )
        session = mcp_sessions.connect_transport(
            transport=str(row.get("transport") or "stdio"),
            command=row.get("command") or (recipe.command if recipe else None),
            args=args,
            url=row.get("url") or (recipe.url if recipe else None),
            env=env,
            cwd=root,
            headers=headers,
        )
        try:
            tools = session.list_tools()
        finally:
            session.close()
        row["status"] = "ok"
        row["cached_tools"] = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]
        _save(row)
        return "ok", None
    except AppError as exc:
        row["status"] = "error"
        _save(row)
        raise exc
    except Exception:
        row["status"] = "error"
        _save(row)
        return "error", "mcp.ping.failed"
