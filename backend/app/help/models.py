from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.http.app import ApiModel


class HelpChatStatus(ApiModel):
    configured: bool
    onboarding_seen: bool = Field(alias="onboardingSeen")
    web_search_enabled: bool = Field(alias="webSearchEnabled")
    degraded: bool = False


class HelpSource(ApiModel):
    kind: Literal["rag", "web"]
    title: str
    section: str | None = None
    url: str | None = None


class HelpMessage(ApiModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str = Field(alias="createdAt")
    sources: list[HelpSource] | None = None


class HelpSendBody(ApiModel):
    text: str


class HelpMessageList(ApiModel):
    items: list[HelpMessage]


class HelpReindexResult(ApiModel):
    state: Literal["ready", "error"]
    message_key: str | None = Field(default=None, alias="messageKey")
