"""Help-chat RAG chunks. Separate from workspace network_rag."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.blob import pack_f32, unpack_f32
from app.db.engine import locked, transaction


@dataclass
class HelpRagChunk:
    id: str
    source: str | None
    section: str | None
    text: str
    file_hash: str | None
    embedding: list[float]
    embedding_model_id: str | None
    dimension: int | None
    locale: str | None = None
    embedding_provider: str | None = None


def _from_row(row: Any) -> HelpRagChunk:
    keys = row.keys()
    return HelpRagChunk(
        id=row["id"],
        source=row["source"],
        section=row["section"],
        text=row["text"],
        file_hash=row["file_hash"],
        embedding=unpack_f32(row["embedding"]),
        embedding_model_id=row["embedding_model_id"],
        dimension=row["dimension"],
        locale=row["locale"] if "locale" in keys else None,
        embedding_provider=row["embedding_provider"] if "embedding_provider" in keys else None,
    )


def replace_all_chunks(chunks: list[HelpRagChunk]) -> None:
    with transaction("help") as conn:
        conn.execute("DELETE FROM help_chat_rag_chunks")
        for chunk in chunks:
            conn.execute(
                """
                INSERT INTO help_chat_rag_chunks (
                  id, source, section, text, file_hash,
                  embedding, embedding_model_id, dimension, locale,
                  embedding_provider
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.id,
                    chunk.source,
                    chunk.section,
                    chunk.text,
                    chunk.file_hash,
                    pack_f32(chunk.embedding),
                    chunk.embedding_model_id,
                    chunk.dimension,
                    chunk.locale,
                    chunk.embedding_provider,
                ),
            )


def list_all_chunks() -> list[HelpRagChunk]:
    with locked("help") as conn:
        rows = conn.execute(
            "SELECT * FROM help_chat_rag_chunks ORDER BY id"
        ).fetchall()
        return [_from_row(row) for row in rows]


def wipe_chunks() -> None:
    with transaction("help") as conn:
        conn.execute("DELETE FROM help_chat_rag_chunks")
