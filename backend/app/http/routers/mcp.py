from __future__ import annotations

from fastapi import APIRouter, Response

from app.mcp.models import (
    McpEnabledBody,
    McpPingResult,
    McpRecipeList,
    McpServerCreate,
    McpServerList,
    McpServerListItem,
    McpServerPatch,
)
from app.mcp.service import (
    create_server,
    delete_server,
    list_recipes,
    list_servers,
    patch_server,
    ping_server,
    set_enabled,
)

router = APIRouter(tags=["mcp"])


@router.get("/mcp/recipes", response_model=McpRecipeList)
def get_recipes() -> McpRecipeList:
    return McpRecipeList(items=list_recipes())


@router.get("/mcp/servers", response_model=McpServerList)
def get_servers() -> McpServerList:
    return McpServerList(items=list_servers())


@router.post("/mcp/servers", response_model=McpServerListItem, status_code=201)
def post_server(body: McpServerCreate) -> McpServerListItem:
    return create_server(body)


@router.patch("/mcp/servers/{server_id}", response_model=McpServerListItem)
def patch_server_route(server_id: str, body: McpServerPatch) -> McpServerListItem:
    return patch_server(server_id, body)


@router.post("/mcp/servers/{server_id}/enabled", response_model=McpServerListItem)
def post_enabled(server_id: str, body: McpEnabledBody) -> McpServerListItem:
    return set_enabled(server_id, body.enabled)


@router.post("/mcp/servers/{server_id}/ping", response_model=McpPingResult, response_model_exclude_none=True)
def post_ping(server_id: str) -> McpPingResult:
    status, key = ping_server(server_id)
    return McpPingResult(status=status, message_key=key)


@router.delete("/mcp/servers/{server_id}", status_code=204)
def delete_server_route(server_id: str) -> Response:
    delete_server(server_id)
    return Response(status_code=204)
