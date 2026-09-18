"""Runtime DTOs. camelCase aliases; ``secret`` never serializes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.common.types import Provider
from app.http.app import ApiModel


class PingResult(ApiModel):
    ok: bool
    message_key: str | None = Field(default=None, alias="messageKey")


class OllamaModel(ApiModel):
    name: str
    size_bytes: int | None = Field(default=None, alias="sizeBytes")


class ToolCall(ApiModel):
    id: str
    name: str
    arguments: str


class ChatMessage(ApiModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = Field(default=None, alias="toolCallId")
    tool_calls: list[ToolCall] | None = Field(default=None, alias="toolCalls")


class CompletionUsage(ApiModel):
    prompt_tokens: int = Field(alias="promptTokens")
    completion_tokens: int = Field(alias="completionTokens")


class CompletionRequest(ApiModel):
    provider: Provider
    model: str
    messages: list[ChatMessage]
    base_url: str | None = Field(default=None, alias="baseUrl")
    credential_id: str | None = Field(default=None, alias="credentialId")
    secret: str | None = Field(default=None, exclude=True)
    temperature: float | None = None
    max_tokens: int | None = Field(default=None, alias="maxTokens")
    tools: list[dict[str, Any]] | None = None
    timeout_sec: float = 120.0
    ollama_options: dict[str, Any] | None = None


class CompletionResult(ApiModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list, alias="toolCalls")
    finish_reason: str | None = Field(default=None, alias="finishReason")
    usage: CompletionUsage | None = None
    model: str


class StreamEvent(ApiModel):
    kind: Literal["delta", "tool_call_delta", "usage", "done", "error"]
    text: str | None = None
    tool_calls: list[ToolCall] | None = Field(default=None, alias="toolCalls")
    usage: CompletionUsage | None = None
    finish_reason: str | None = Field(default=None, alias="finishReason")
    error_key: str | None = Field(default=None, alias="errorKey")


class EmbedRequest(ApiModel):
    texts: list[str]
    model: str
    provider: Provider = "ollama"
    base_url: str | None = Field(default=None, alias="baseUrl")
    credential_id: str | None = Field(default=None, alias="credentialId")
    secret: str | None = Field(default=None, exclude=True)
    timeout_sec: float = 60.0


class EmbedResult(ApiModel):
    vectors: list[list[float]]
    dimension: int
    model: str


class TestLlmRequest(ApiModel):
    provider: Provider
    model: str
    base_url: str | None = Field(default=None, alias="baseUrl")
    credential_id: str | None = Field(default=None, alias="credentialId")


class RuntimeModelOut(ApiModel):
    name: str
    size_bytes: int | None = Field(default=None, alias="sizeBytes")


class RuntimeModelsResponse(ApiModel):
    items: list[RuntimeModelOut]
