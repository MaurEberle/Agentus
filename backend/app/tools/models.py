from __future__ import annotations

from typing import Any

from pydantic import Field

from app.http.app import ApiModel
from app.tools.kinds import FirstPartyKind


class CatalogTool(ApiModel):
    name: str
    kind: FirstPartyKind | None = None
    description: str | None = None
    json_schema: dict[str, Any] | None = Field(default=None, alias="jsonSchema")
    credential_kind: str | None = Field(default=None, alias="credentialKind")
    server_id: str | None = Field(default=None, alias="serverId")
    mcp_tool_name: str | None = Field(default=None, alias="mcpToolName")
    title_key: str | None = Field(default=None, alias="titleKey")
    description_key: str | None = Field(default=None, alias="descriptionKey")


class CatalogGroup(ApiModel):
    id: str
    title_key: str | None = Field(default=None, alias="titleKey")
    tools: list[CatalogTool]


class CatalogResponse(ApiModel):
    groups: list[CatalogGroup]


class ExecuteResult(ApiModel):
    ok: bool
    result: Any = None
    error_key: str | None = Field(default=None, alias="errorKey")
