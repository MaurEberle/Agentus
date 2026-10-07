"""Compact ask payload for run wait notifications."""

from __future__ import annotations

ASK_EXCERPT_MAX = 120


def excerpt(text: str, limit: int = ASK_EXCERPT_MAX) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    cut = max(1, limit - 1)
    return compact[:cut].rstrip() + "…"
