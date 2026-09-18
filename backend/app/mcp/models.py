from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.http.app import ApiModel

McpTransport = Literal["stdio", "http"]
McpServerStatus = Literal["unknown", "ok", "error", "runtime_missing"]


class McpToolInfo(ApiModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict, alias="inputSchema")


class McpRecipe(ApiModel):
    id: str
    title_key: str = Field(alias="titleKey")
    transport: McpTransport
    credential_kinds: list[str] = Field(default_factory=list, alias="credentialKinds")
    needs_root: bool = Field(alias="needsRoot")


class McpServerListItem(ApiModel):
    id: str
    recipe_id: str | None = Field(default=None, alias="recipeId")
    name: str
    transport: McpTransport
    enabled: bool
    status: McpServerStatus
    credential_ids: list[str] | None = Field(default=None, alias="credentialIds")
    root_path: str | None = Field(default=None, alias="rootPath")


class McpServerCreate(ApiModel):
    recipe_id: str | None = Field(default=None, alias="recipeId")
    name: str | None = None
    transport: McpTransport | None = None
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    credential_ids: list[str] | None = Field(default=None, alias="credentialIds")
    root_path: str | None = Field(default=None, alias="rootPath")
    enabled: bool = False


class McpServerPatch(ApiModel):
    name: str | None = None
    enabled: bool | None = None
    credential_ids: list[str] | None = Field(default=None, alias="credentialIds")
    root_path: str | None = Field(default=None, alias="rootPath")
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    transport: McpTransport | None = None


class McpEnabledBody(ApiModel):
    enabled: bool


class McpPingResult(ApiModel):
    status: McpServerStatus
    message_key: str | None = Field(default=None, alias="messageKey")


class McpRecipeList(ApiModel):
    items: list[McpRecipe]


class McpServerList(ApiModel):
    items: list[McpServerListItem]
