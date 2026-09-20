from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

from app.db.engine import get_bootstrap
from app.db.help_rag import HelpRagChunk, list_all_chunks, replace_all_chunks, wipe_chunks
from app.db.paths import RAG_DIR_NAME
from app.help.chunk import chunk_markdown, file_sha256
from app.help.status import get_settings_merged
from app.runtime.errors import RuntimeApiError
from app.runtime.models import EmbedRequest

DEFAULT_EMBED_MODEL = "nomic-embed-text"
SCORE_MIN = 0.22
TOP_K = 6


def corpus_dir() -> Path:
    bootstrap = get_bootstrap()
    return (Path(bootstrap.data_dir) / RAG_DIR_NAME).resolve()


def _iter_corpus_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".sqlite":
            continue
        try:
            resolved = path.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        suffix = path.suffix.lower()
        if suffix in {".md", ".txt"}:
            out.append(path)
        elif suffix == ".pdf":
            try:
                import pypdf  # noqa: F401
            except ImportError:
                continue
            out.append(path)
    return out


def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _build_chunks() -> list[HelpRagChunk]:
    root = corpus_dir()
    built: list[HelpRagChunk] = []
    for path in _iter_corpus_files(root):
        raw = _read_file(path)
        if not raw.strip():
            continue
        digest = file_sha256(path)
        title = path.stem
        for piece in chunk_markdown(raw, title, digest):
            built.append(
                HelpRagChunk(
                    id=str(uuid.uuid4()),
                    source=piece.title,
                    section=piece.section,
                    text=piece.text,
                    file_hash=piece.file_hash,
                    embedding=[],
                    embedding_model_id=None,
                    dimension=None,
                )
            )
    return built


def index_is_ready() -> bool:
    chunks = list_all_chunks()
    if not chunks:
        return False
    return any((chunk.dimension or 0) > 0 and chunk.embedding for chunk in chunks)


def reindex() -> tuple[Literal["ready", "error"], str | None]:
    from app.runtime.embeddings import embed

    settings = get_settings_merged()
    help_chat = settings.help_chat
    provider = help_chat.embedding_provider or "ollama"
    model = help_chat.embedding_model.strip() or DEFAULT_EMBED_MODEL
    if provider in {"xai", "anthropic"}:
        return "error", "help.embed.unsupported"
    credential_id = None
    if provider != "ollama":
        if not help_chat.credential_id:
            return "error", "help.embed.unsupported"
        credential_id = help_chat.credential_id
    chunks = _build_chunks()
    if not chunks:
        wipe_chunks()
        return "ready", None
    try:
        result = embed(
            EmbedRequest(
                texts=[chunk.text for chunk in chunks],
                model=model,
                provider=provider,  # type: ignore[arg-type]
                credential_id=credential_id,
            )
        )
    except RuntimeApiError:
        return "error", "help.index.failed"
    except Exception:
        return "error", "help.index.failed"
    if len(result.vectors) != len(chunks):
        return "error", "help.index.failed"
    dimension = result.dimension
    stored: list[HelpRagChunk] = []
    for chunk, vector in zip(chunks, result.vectors, strict=True):
        stored.append(
            HelpRagChunk(
                id=chunk.id,
                source=chunk.source,
                section=chunk.section,
                text=chunk.text,
                file_hash=chunk.file_hash,
                embedding=vector,
                embedding_model_id=model,
                dimension=dimension,
            )
        )
    replace_all_chunks(stored)
    return "ready", None
