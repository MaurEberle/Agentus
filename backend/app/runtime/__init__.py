"""Inference client. Help and harness import these functions only."""

from app.runtime.completions import complete, complete_stream, test_llm
from app.runtime.embeddings import embed
from app.runtime.models import (
    ChatMessage,
    CompletionRequest,
    CompletionResult,
    EmbedRequest,
    EmbedResult,
    PingResult,
    StreamEvent,
    TestLlmRequest,
)
from app.runtime.ollama import (
    ensure_loaded,
    list_loaded_models,
    list_ollama_models,
    ping_ollama,
    unload,
)

__all__ = [
    "ChatMessage",
    "CompletionRequest",
    "CompletionResult",
    "EmbedRequest",
    "EmbedResult",
    "PingResult",
    "StreamEvent",
    "TestLlmRequest",
    "complete",
    "complete_stream",
    "embed",
    "ensure_loaded",
    "list_loaded_models",
    "list_ollama_models",
    "ping_ollama",
    "test_llm",
    "unload",
]
