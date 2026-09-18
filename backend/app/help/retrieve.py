from __future__ import annotations

import math

from app.db.help_rag import list_all_chunks
from app.help.index import SCORE_MIN, TOP_K
from app.help.models import HelpSource
from app.help.status import get_settings_merged
from app.runtime.models import EmbedRequest


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def retrieve_scored(query: str) -> list[tuple[float, HelpSource]]:
    chunks = list_all_chunks()
    if not chunks:
        return []
    settings = get_settings_merged()
    help_chat = settings.help_chat
    provider = help_chat.embedding_provider or "ollama"
    model = help_chat.embedding_model.strip() or "nomic-embed-text"
    if provider == "xai":
        return []
    credential_id = help_chat.credential_id if provider == "openai_compat" else None
    from app.runtime.embeddings import embed

    try:
        result = embed(
            EmbedRequest(
                texts=[query],
                model=model,
                provider=provider,  # type: ignore[arg-type]
                credential_id=credential_id,
            )
        )
    except Exception:
        return []
    if not result.vectors:
        return []
    query_vec = result.vectors[0]
    scored: list[tuple[float, HelpSource]] = []
    for chunk in chunks:
        score = cosine(query_vec, chunk.embedding)
        if score < SCORE_MIN:
            continue
        scored.append(
            (
                score,
                HelpSource(
                    kind="rag",
                    title=chunk.source or "",
                    section=chunk.section,
                ),
            )
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:TOP_K]


def retrieve(query: str) -> list[HelpSource]:
    return [source for _score, source in retrieve_scored(query)]
