"""HTTP/domain Pydantic models. Aliases camelCase; patch root forbids extras."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.common.types import (
    CredentialKind,
    DataDirSource,
    EmbeddingProvider,
    HelpProvider,
    ServiceStatus,
    StoreId,
)
from app.http.app import ApiModel


class HelpChatSettings(ApiModel):
    provider: HelpProvider = ""
    model: str = ""
    credential_id: str | None = Field(default=None, alias="credentialId")
    embedding_provider: EmbeddingProvider = Field(default="", alias="embeddingProvider")
    embedding_model: str = Field(default="", alias="embeddingModel")
    web_search_enabled: bool = Field(default=False, alias="webSearchEnabled")
    web_search_credential_id: str | None = Field(default=None, alias="webSearchCredentialId")
    fallback_model: str | None = Field(default=None, alias="fallbackModel")


class AppSettings(ApiModel):
    ollama_base_url: str = Field(alias="ollamaBaseUrl")
    openai_compat_base_url: str | None = Field(default=None, alias="openaiCompatBaseUrl")
    help_chat_fab_visible: bool = Field(default=True, alias="helpChatFabVisible")
    help_chat: HelpChatSettings = Field(default_factory=HelpChatSettings, alias="helpChat")
    active_network_id: str | None = Field(default=None, alias="activeNetworkId")
    history_retention_days: int | None = Field(default=90, alias="historyRetentionDays")
    chat_onboarding_seen: bool = Field(default=False, alias="chatOnboardingSeen")


class AppSettingsPatch(ApiModel):
    """All fields optional; helpChat is a partial dict (nested merge in service)."""

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        ser_json_by_alias=True,
        extra="forbid",
    )

    ollama_base_url: str | None = Field(default=None, alias="ollamaBaseUrl")
    openai_compat_base_url: str | None = Field(default=None, alias="openaiCompatBaseUrl")
    help_chat_fab_visible: bool | None = Field(default=None, alias="helpChatFabVisible")
    help_chat: dict[str, Any] | None = Field(default=None, alias="helpChat")
    active_network_id: str | None = Field(default=None, alias="activeNetworkId")
    history_retention_days: int | None = Field(default=None, alias="historyRetentionDays")
    chat_onboarding_seen: bool | None = Field(default=None, alias="chatOnboardingSeen")


class CredentialListItem(ApiModel):
    id: str
    name: str
    kind: CredentialKind
    mask: str
    in_use: bool = Field(alias="inUse")


class CredentialListResponse(ApiModel):
    items: list[CredentialListItem]


class CredentialCreate(ApiModel):
    name: str
    kind: CredentialKind
    secret: str

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("required")
        return stripped


class CredentialPatch(ApiModel):
    name: str | None = None
    kind: CredentialKind | None = None
    secret: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("required")
        return stripped


class StoreStatus(ApiModel):
    id: StoreId
    file_name: str = Field(alias="fileName")
    ok: bool
    state: Literal["ok", "missing", "error"]
    message_key: str | None = Field(default=None, alias="messageKey")


class DataLocation(ApiModel):
    data_dir: str = Field(alias="dataDir")
    source: DataDirSource
    read_only: bool | None = Field(default=None, alias="readOnly")
    stores: list[StoreStatus]


class DataLocationPost(ApiModel):
    path: str
    copy_files: bool = Field(default=False, alias="copy")


class SessionOut(ApiModel):
    active_network_id: str | None = Field(alias="activeNetworkId")
    active_network_name: str | None = Field(default=None, alias="activeNetworkName")
    service_status: ServiceStatus = Field(alias="serviceStatus")
    run_id: str | None = Field(default=None, alias="runId")
    started_at: str | None = Field(default=None, alias="startedAt")


class ActiveNetworkPut(ApiModel):
    network_id: str | None = Field(alias="networkId")
