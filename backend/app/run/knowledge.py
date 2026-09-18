from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.db.engine import utc_now
from app.db.network_rag import (
    CollectionMeta,
    RagChunk,
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


@dataclass
class Snippet:
    title: str
    section: str | None
    text: str
    score: float


def drop_node(network_id: str, node_id: str) -> None:
    db_drop_node(network_id, node_id)


def drop_network(network_id: str) -> None:
    db_drop_network(network_id)


def status_for_network(network_id: str) -> list[dict[str, str]]:
    return [
        {"nodeId": item.node_id, "state": item.state}
        for item in list_collection_states(network_id)
    ]


def _safe_files(root: Path, data_dir: str) -> list[Path]:
    data_root = Path(os.path.realpath(data_dir))
    if not root.exists():
        return []
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
            resolved.relative_to(data_root)
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


def _read(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader

            return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        except Exception:
            return ""
    return path.read_text(encoding="utf-8", errors="replace")


def index_node(
    network_id: str,
    node: GraphNode,
    *,
    data_dir: str,
    force: bool = False,
) -> Literal["ready", "error"]:
    from app.runtime.embeddings import embed

    source = str(node.data.get("sourcePath") or "")
    if not source:
        return "error"
    root = Path(os.path.realpath(source))
    files = _safe_files(root, data_dir)
    digest = hashlib.sha256()
    texts: list[tuple[str, str | None, str, str]] = []
    for path in files:
        raw = _read(path)
        if not raw.strip():
            continue
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(file_hash.encode())
        title = path.stem
        for piece in chunk_markdown(raw, title, file_hash):
            texts.append((piece.title, piece.section, piece.text, piece.file_hash))
    model = DEFAULT_EMBED_MODEL
    existing = get_collection(network_id, node.id)
    combo = digest.hexdigest()
    if (
        not force
        and existing
        and existing.state == "ready"
        and existing.embedding_model_id == model
        and existing.source_path == source
    ):
        return "ready"
    if not texts:
        upsert_collection(
            CollectionMeta(
                network_id=network_id,
                node_id=node.id,
                source_path=source,
                embedding_model_id=model,
                dimension=0,
                state="ready",
                updated_at=utc_now(),
            )
        )
        replace_chunks(network_id, node.id, [])
        return "ready"
    try:
        result = embed(
            EmbedRequest(
                texts=[t[2] for t in texts],
                model=model,
                provider="ollama",
            )
        )
    except Exception:
        upsert_collection(
            CollectionMeta(
                network_id=network_id,
                node_id=node.id,
                source_path=source,
                embedding_model_id=model,
                dimension=None,
                state="error",
                updated_at=utc_now(),
            )
        )
        return "error"
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
        for (title, section, text, file_hash), vector in zip(texts, result.vectors, strict=False)
    ]
    upsert_collection(
        CollectionMeta(
            network_id=network_id,
            node_id=node.id,
            source_path=source,
            embedding_model_id=model,
            dimension=result.dimension,
            state="ready",
            updated_at=utc_now(),
        )
    )
    replace_chunks(network_id, node.id, chunks)
    return "ready"


def retrieve(
    network_id: str,
    node_id: str,
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    score_min: float = DEFAULT_SCORE_MIN,
) -> list[Snippet]:
    from app.runtime.embeddings import embed

    chunks = list_chunks(network_id, node_id)
    if not chunks:
        return []
    try:
        result = embed(
            EmbedRequest(texts=[query], model=DEFAULT_EMBED_MODEL, provider="ollama")
        )
    except Exception:
        return []
    if not result.vectors:
        return []
    qv = result.vectors[0]
    scored: list[Snippet] = []
    for chunk in chunks:
        score = cosine(qv, chunk.embedding)
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
