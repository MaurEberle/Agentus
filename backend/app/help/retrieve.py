from __future__ import annotations

import math

from app.db.help_rag import HelpRagChunk, list_all_chunks
from app.help.index import SCORE_MIN, TOP_K
from app.help.locales import resolve_help_locale
from app.help.models import HelpSource
from app.help.status import get_settings_merged
from app.runtime.models import EmbedRequest


def _chunks_for_locale(chunks: list[HelpRagChunk], locale: str | None) -> list[HelpRagChunk]:
    wanted = resolve_help_locale(locale)
    unscoped = [chunk for chunk in chunks if not chunk.locale]
    localized = [chunk for chunk in chunks if chunk.locale == wanted]
    if not localized and wanted != "de":
        localized = [chunk for chunk in chunks if chunk.locale == "de"]
    if not localized and wanted != "en":
        localized = [chunk for chunk in chunks if chunk.locale == "en"]
    pooled = localized + unscoped
    return pooled if pooled else chunks


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


def retrieve_scored(query: str, locale: str | None = None) -> list[tuple[float, HelpSource]]:
    chunks = _chunks_for_locale(list_all_chunks(), locale)
    if not chunks:
        return []
    settings = get_settings_merged()
    help_chat = settings.help_chat
    provider = help_chat.embedding_provider or "ollama"
    model = help_chat.embedding_model.strip() or "nomic-embed-text"
    if provider == "xai" or provider == "anthropic":
        return []
    credential_id = None
    if provider != "ollama":
        credential_id = help_chat.embedding_credential_id or (
            help_chat.credential_id if help_chat.provider == provider else None
        )
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


def retrieve(query: str, locale: str | None = None) -> list[HelpSource]:
    return [source for _score, source in retrieve_scored(query, locale)]
