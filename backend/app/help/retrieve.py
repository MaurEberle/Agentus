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


def _query_target(chunks: list[HelpRagChunk]) -> tuple[str, str, str | None] | None:
    """Embed the question with the model that produced the stored vectors.

    Settings may already point at a new provider while reindex has not written
    yet. Querying that model against the old blobs scores as zero or errors.
    """
    settings = get_settings_merged()
    help_chat = settings.help_chat
    settings_provider = help_chat.embedding_provider or "ollama"
    settings_model = help_chat.embedding_model.strip() or "nomic-embed-text"
    stored_models = {chunk.embedding_model_id for chunk in chunks if chunk.embedding_model_id}
    stored_providers = {chunk.embedding_provider for chunk in chunks if chunk.embedding_provider}
    provider = settings_provider
    model = settings_model
    if len(stored_models) == 1:
        stored_model = next(iter(stored_models))
        if stored_model != settings_model or stored_providers:
            model = stored_model
            if len(stored_providers) == 1:
                provider = next(iter(stored_providers))
            elif stored_model != settings_model:
                provider = "ollama"
    if provider in {"xai", "anthropic"}:
        return None
    credential_id = None
    if provider != "ollama":
        if provider == settings_provider:
            credential_id = help_chat.embedding_credential_id or (
                help_chat.credential_id if help_chat.provider == provider else None
            )
        elif help_chat.provider == provider:
            credential_id = help_chat.credential_id
    return provider, model, credential_id


def retrieve_scored(query: str, locale: str | None = None) -> list[tuple[float, HelpSource, str]]:
    chunks = _chunks_for_locale(list_all_chunks(), locale)
    if not chunks:
        return []
    target = _query_target(chunks)
    if target is None:
        return []
    provider, model, credential_id = target
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
    scored: list[tuple[float, HelpSource, str]] = []
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
                chunk.text,
            )
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:TOP_K]


def retrieve(query: str, locale: str | None = None) -> list[HelpSource]:
    return [item[1] for item in retrieve_scored(query, locale)]
