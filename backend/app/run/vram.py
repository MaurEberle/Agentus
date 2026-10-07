"""Keep Ollama VRAM to the active chat model plus help and one embedding."""

from __future__ import annotations

from typing import Any


def resident_tags(
    settings: Any,
    compiled: Any | None = None,
    current: str | None = None,
) -> set[str]:
    keep: set[str] = set()
    model = (current or "").strip()
    if model:
        keep.add(model)
    help_chat = getattr(settings, "help_chat", None)
    if help_chat is not None:
        if getattr(help_chat, "provider", "") == "ollama":
            primary = (getattr(help_chat, "model", None) or "").strip()
            if primary:
                keep.add(primary)
        embed_provider = getattr(help_chat, "embedding_provider", "") or "ollama"
        embed = (getattr(help_chat, "embedding_model", None) or "").strip()
        if embed and embed_provider == "ollama":
            keep.add(embed)
    if compiled is not None:
        by_id = getattr(compiled, "by_id", {}) or {}
        for node in by_id.values():
            if getattr(node, "type", None) != "knowledge":
                continue
            data = getattr(node, "data", None) or {}
            provider = str(data.get("embeddingProvider") or "ollama")
            embed = str(data.get("embeddingModel") or "").strip()
            if provider == "ollama" and embed:
                keep.add(embed)
    return keep


def release_others(
    settings: Any,
    compiled: Any | None = None,
    current: str | None = None,
) -> list[str]:
    from app.runtime.ollama import keep_only

    keep = resident_tags(settings, compiled, current)
    try:
        return keep_only(keep)
    except Exception:
        return []
