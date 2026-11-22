from __future__ import annotations

import dataclasses
import hashlib
import logging
import math
import operator
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Any, Literal

from app.common import extract as extract_mod
from app.common.extract import extract_text, is_indexable
from app.db.engine import utc_now
from app.db.paths import RAG_DIR_NAME
from app.db.network_rag import (
    CollectionMeta,
    RagChunk,
    chunk_stamp,
    get_collection,
    list_chunks,
    list_collection_states,
    replace_chunks,
    upsert_collection,
)
from app.db.network_rag import drop_network as db_drop_network
from app.db.network_rag import drop_node as db_drop_node
from app.help.chunk import chunk_markdown
from app.help.retrieve import cosine
from app.run.graph_models import GraphNode
from app.run.limits import DEFAULT_EMBED_MODEL, DEFAULT_SCORE_MIN, DEFAULT_TOP_K, KNOWLEDGE_CHUNK_CHARS
from app.runtime.models import EmbedRequest

_EMBED_PROVIDERS = frozenset({"ollama", "openai", "gemini", "openai_compat"})

log = logging.getLogger("agentus.knowledge")

# M22: a folder with more files than this is cut (sorted by path) and says so.
MAX_INDEX_FILES = 5_000

# M22: vectors per collection, keyed by a cheap change marker. retrieve() used to
# load every vector from SQLite on each agent turn.
_VECTORS: dict[tuple[str, str], tuple[tuple, list[tuple[RagChunk, float]]]] = {}
_VECTORS_LOCK = threading.Lock()


def reset_vector_cache() -> None:
    with _VECTORS_LOCK:
        _VECTORS.clear()


def _embed_args(node: GraphNode) -> tuple[str, str, str | None]:
    provider = str(node.data.get("embeddingProvider") or "ollama").strip() or "ollama"
    if provider not in _EMBED_PROVIDERS:
        provider = "ollama"
    model = str(node.data.get("embeddingModel") or "").strip() or DEFAULT_EMBED_MODEL
    credential_id = str(node.data.get("embeddingCredentialId") or "").strip() or None
    if provider == "ollama":
        credential_id = None
    return provider, model, credential_id


@dataclass
class Snippet:
    title: str
    section: str | None
    text: str
    score: float


def drop_node(network_id: str, node_id: str) -> None:
    reset_vector_cache()
    db_drop_node(network_id, node_id)


def drop_network(network_id: str) -> None:
    reset_vector_cache()
    db_drop_network(network_id)


def status_for_network(network_id: str) -> list[dict[str, str]]:
    return [
        {"nodeId": item.node_id, "state": item.state}
        for item in list_collection_states(network_id)
    ]


def _resolved_dir(raw: str) -> Path | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return Path(os.path.realpath(os.path.expanduser(text)))
    except (OSError, ValueError):
        return None


def _is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent)
        return True
    except (OSError, ValueError):
        return False


def _path_parts(path: Path) -> list[str]:
    return str(path).replace("\\", "/").split("/")


def source_block_reason(source_path: str, data_dir: str) -> str | None:
    """``path``, ``corpus``, or ``data`` when the folder must not be indexed."""
    from app.tools.file_access_tool import is_forbidden_root

    raw = (source_path or "").strip()
    if not raw:
        return "path"
    expanded = os.path.expanduser(raw)
    if not os.path.isabs(expanded):
        return "path"
    real = _resolved_dir(expanded)
    if real is None or is_forbidden_root(Path(real)):
        return "path"
    if RAG_DIR_NAME in _path_parts(real):
        return "corpus"
    data = _resolved_dir(data_dir)
    if data is not None and (real == data or _is_under(real, data)):
        return "data"
    return None


def source_is_allowed(source_path: str, data_dir: str) -> bool:
    return source_block_reason(source_path, data_dir) is None


def _same_source(stored: str | None, source: str) -> bool:
    left = _resolved_dir(stored or "")
    right = _resolved_dir(source)
    return left is not None and left == right


def _safe_files(root: Path, data_dir: str) -> list[Path]:
    try:
        source_root = Path(os.path.realpath(root))
    except OSError:
        return []
    if not source_root.is_dir():
        return []
    if not source_is_allowed(str(source_root), data_dir):
        return []
    data = _resolved_dir(data_dir)
    out: list[Path] = []
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
            resolved.relative_to(source_root)
        except (OSError, ValueError):
            continue
        if data is not None and (resolved == data or _is_under(resolved, data)):
            continue
        if RAG_DIR_NAME in _path_parts(resolved):
            continue
        if is_indexable(path):
            out.append(path)
    return out


def _fingerprint(root: Path, files: list[Path]) -> str:
    """Relative path, size and modification time. Any add, delete, edit, or rename changes it.

    M22: no file is read for it; the bytes are hashed once per changed file below.
    """
    rows: list[str] = []
    for path in files:
        try:
            resolved = path.resolve()
            rel = resolved.relative_to(root).as_posix()
            stat = path.stat()
        except (OSError, ValueError):
            return ""
        rows.append(f"{rel}\t{stat.st_size}\t{stat.st_mtime_ns}")
    rows.sort()
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _reusable(network_id: str, node_id: str, model: str) -> dict[str, list[RagChunk]]:
    """M22: chunks of the last index by file hash; unchanged files keep their vectors."""
    found: dict[str, list[RagChunk]] = {}
    try:
        chunks = list_chunks(network_id, node_id)
    except Exception:
        return found
    for chunk in chunks:
        if chunk.file_hash and chunk.embedding_model_id == model and chunk.embedding:
            found.setdefault(chunk.file_hash, []).append(chunk)
    return found


def _error_key(exc: BaseException) -> str:
    key = getattr(exc, "error_key", None)
    return key if isinstance(key, str) and key else "runtime.upstream"


def _read(path: Path) -> str:
    return extract_text(path)


def _file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _too_large(path: Path) -> bool:
    size = _file_size(path)
    return size is not None and size > extract_mod.MAX_SOURCE_BYTES


def index_node(
    network_id: str,
    node: GraphNode,
    *,
    data_dir: str,
    force: bool = False,
    on_progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> Literal["ready", "error"]:
    from app.runtime.embeddings import embed

    def tell(phase: str, **payload: Any) -> None:
        if on_progress is not None:
            on_progress(phase, payload)

    source = str(node.data.get("sourcePath") or "")
    if not source:
        return "error"
    provider, model, credential_id = _embed_args(node)
    if not source_is_allowed(source, data_dir):
        _mark_index_error(network_id, node.id, source, model)
        return "error"
    root = Path(os.path.realpath(source))
    files = sorted(_safe_files(root, data_dir), key=lambda item: item.as_posix())
    if len(files) > MAX_INDEX_FILES:
        log.warning("knowledge folder %s has %s files; indexing %s", source, len(files), MAX_INDEX_FILES)
        tell("limit", files=len(files), max=MAX_INDEX_FILES)
        files = files[:MAX_INDEX_FILES]
    fingerprint = _fingerprint(root, files)
    if not fingerprint and files:
        _mark_index_error(network_id, node.id, source, model)
        return "error"
    existing = get_collection(network_id, node.id)
    # A previous pass can store "ready" with no vectors when every file was
    # skipped. That must not stick just because the file bytes are unchanged.
    stale_empty = bool(files) and existing is not None and (existing.dimension or 0) == 0
    if (
        not force
        and existing
        and not stale_empty
        and existing.state == "ready"
        and existing.embedding_model_id == model
        and existing.content_fingerprint == fingerprint
        and _same_source(existing.source_path, source)
    ):
        tell("cached")
        return "ready"
    tell("read")
    # A forced reindex rebuilds everything; otherwise unchanged files reuse their vectors.
    previous = {} if force else _reusable(network_id, node.id, model)
    texts: list[tuple[str, str | None, str, str]] = []
    reused: list[RagChunk] = []
    saw_oversized = False
    saw_readable = False
    for path in files:
        if _too_large(path):
            saw_oversized = True
            continue
        saw_readable = True
        try:
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        title = path.stem
        old = previous.get(file_hash)
        if old:
            reused.extend(
                dataclasses.replace(chunk, id=str(uuid.uuid4()), source=title) for chunk in old
            )
            continue
        raw = _read(path)
        if not raw.strip():
            continue
        for piece in chunk_markdown(raw, title, file_hash):
            texts.append((piece.title, piece.section, piece.text, piece.file_hash))
    if not texts and reused:
        upsert_collection(
            CollectionMeta(
                network_id=network_id,
                node_id=node.id,
                source_path=source,
                embedding_model_id=model,
                dimension=reused[0].dimension,
                state="ready",
                updated_at=utc_now(),
                content_fingerprint=fingerprint,
            )
        )
        replace_chunks(network_id, node.id, reused)
        reset_vector_cache()
        tell("ready", chunks=len(reused), reused=len(reused))
        return "ready"
    if not texts:
        if saw_oversized and not saw_readable:
            tell("error", error="knowledge.tooLarge")
            _mark_index_error(network_id, node.id, source, model)
            return "error"
        upsert_collection(
            CollectionMeta(
                network_id=network_id,
                node_id=node.id,
                source_path=source,
                embedding_model_id=model,
                dimension=0,
                state="ready",
                updated_at=utc_now(),
                content_fingerprint=fingerprint,
            )
        )
        replace_chunks(network_id, node.id, [])
        reset_vector_cache()
        tell("ready", chunks=0)
        return "ready"
    tell("embed", chunks=len(texts), model=model, reused=len(reused))
    try:
        result = embed(
            EmbedRequest(
                texts=[t[2] for t in texts],
                model=model,
                provider=provider,  # type: ignore[arg-type]
                credential_id=credential_id,
            )
        )
    except Exception as exc:
        # M22: the reason used to be lost; the run log only said "failed".
        key = _error_key(exc)
        log.warning("knowledge embedding failed node=%s model=%s key=%s", node.id, model, key, exc_info=True)
        tell("error", error=key, detail=str(getattr(exc, "detail", "") or "")[:200])
        _mark_index_error(network_id, node.id, source, model)
        return "error"
    if len(result.vectors) != len(texts):
        tell("error", error="runtime.embedMismatch")
        _mark_index_error(network_id, node.id, source, model)
        return "error"
    if reused and reused[0].dimension and result.dimension != reused[0].dimension:
        # Same model, other vector size (model replaced under the same name): no mixing.
        return index_node(network_id, node, data_dir=data_dir, force=True, on_progress=on_progress)
    chunks = [
        RagChunk(
            id=str(uuid.uuid4()),
            network_id=network_id,
            node_id=node.id,
            source=title,
            section=section,
            text=text,
            file_hash=file_hash,
            embedding=vector,
            embedding_model_id=model,
            dimension=result.dimension,
        )
        for (title, section, text, file_hash), vector in zip(texts, result.vectors, strict=True)
    ]
    chunks.extend(reused)
    upsert_collection(
        CollectionMeta(
            network_id=network_id,
            node_id=node.id,
            source_path=source,
            embedding_model_id=model,
            dimension=result.dimension,
            state="ready",
            updated_at=utc_now(),
            content_fingerprint=fingerprint,
        )
    )
    replace_chunks(network_id, node.id, chunks)
    reset_vector_cache()
    tell("ready", chunks=len(chunks), reused=len(reused))
    return "ready"


def _mark_index_error(network_id: str, node_id: str, source: str, model: str) -> None:
    upsert_collection(
        CollectionMeta(
            network_id=network_id,
            node_id=node_id,
            source_path=source,
            embedding_model_id=model,
            dimension=None,
            state="error",
            updated_at=utc_now(),
            content_fingerprint=None,
        )
    )


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(map(operator.mul, vector, vector)))


def _cosine_prepared(query: list[float], q_norm: float, vector: list[float], norm: float) -> float:
    if len(query) != len(vector) or q_norm <= 0 or norm <= 0:
        return cosine(query, vector) if len(query) == len(vector) else 0.0
    return sum(map(operator.mul, query, vector)) / (q_norm * norm)


def _prepared_chunks(network_id: str, node_id: str) -> list[tuple[RagChunk, float]]:
    """M22: chunks with their vector norms, loaded once per index state."""
    meta = get_collection(network_id, node_id)
    stamp = (
        meta.updated_at if meta else None,
        meta.content_fingerprint if meta else None,
        *chunk_stamp(network_id, node_id),
    )
    key = (network_id, node_id)
    with _VECTORS_LOCK:
        hit = _VECTORS.get(key)
        if hit is not None and hit[0] == stamp:
            return hit[1]
    prepared = [(chunk, _norm(chunk.embedding)) for chunk in list_chunks(network_id, node_id)]
    with _VECTORS_LOCK:
        _VECTORS[key] = (stamp, prepared)
    return prepared


def retrieve(
    network_id: str,
    node_id: str,
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    score_min: float = DEFAULT_SCORE_MIN,
    node: GraphNode | None = None,
) -> list[Snippet]:
    from app.runtime.embeddings import embed

    prepared = _prepared_chunks(network_id, node_id)
    if not prepared:
        return []
    chunks = [chunk for chunk, _norm in prepared]
    if node is not None:
        provider, model, credential_id = _embed_args(node)
    else:
        provider, model, credential_id = "ollama", (chunks[0].embedding_model_id or DEFAULT_EMBED_MODEL), None
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
    qv = result.vectors[0]
    q_norm = _norm(qv)
    scored: list[Snippet] = []
    for chunk, norm in prepared:
        score = _cosine_prepared(qv, q_norm, chunk.embedding, norm)
        if score < score_min:
            continue
        scored.append(
            Snippet(
                title=chunk.source or "",
                section=chunk.section,
                text=chunk.text[:KNOWLEDGE_CHUNK_CHARS],
                score=score,
            )
        )
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:top_k]
