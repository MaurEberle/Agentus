"""Workspace RAG. Same store/lock as networks. Help RAG is a different store."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.blob import pack_f32, unpack_f32
from app.db.engine import locked, transaction


@dataclass
class CollectionMeta:
    network_id: str
    node_id: str
    source_path: str | None
    embedding_model_id: str | None
    dimension: int | None
    state: str
    updated_at: str | None


@dataclass
class RagChunk:
    id: str
    network_id: str
    node_id: str
    source: str | None
    section: str | None
    text: str
    file_hash: str | None
    embedding: list[float]
    embedding_model_id: str | None
    dimension: int | None


def _collection(row: object) -> CollectionMeta:
    return CollectionMeta(
        network_id=row["network_id"],  # type: ignore[index]
        node_id=row["node_id"],  # type: ignore[index]
        source_path=row["source_path"],  # type: ignore[index]
        embedding_model_id=row["embedding_model_id"],  # type: ignore[index]
        dimension=row["dimension"],  # type: ignore[index]
        state=row["state"],  # type: ignore[index]
        updated_at=row["updated_at"],  # type: ignore[index]
    )


def _chunk(row: object) -> RagChunk:
    return RagChunk(
        id=row["id"],  # type: ignore[index]
        network_id=row["network_id"],  # type: ignore[index]
        node_id=row["node_id"],  # type: ignore[index]
        source=row["source"],  # type: ignore[index]
        section=row["section"],  # type: ignore[index]
        text=row["text"],  # type: ignore[index]
        file_hash=row["file_hash"],  # type: ignore[index]
        embedding=unpack_f32(row["embedding"]),  # type: ignore[index]
        embedding_model_id=row["embedding_model_id"],  # type: ignore[index]
        dimension=row["dimension"],  # type: ignore[index]
    )


def get_collection(network_id: str, node_id: str) -> CollectionMeta | None:
    with locked("workspace") as conn:
        row = conn.execute(
            """
            SELECT * FROM network_rag_collections
            WHERE network_id = ? AND node_id = ?
            """,
            (network_id, node_id),
        ).fetchone()
    return None if row is None else _collection(row)


def upsert_collection(meta: CollectionMeta) -> None:
    with transaction("workspace") as conn:
        conn.execute(
            """
            INSERT INTO network_rag_collections (
              network_id, node_id, source_path, embedding_model_id,
              dimension, state, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(network_id, node_id) DO UPDATE SET
              source_path = excluded.source_path,
              embedding_model_id = excluded.embedding_model_id,
              dimension = excluded.dimension,
              state = excluded.state,
              updated_at = excluded.updated_at
            """,
            (
                meta.network_id,
                meta.node_id,
                meta.source_path,
                meta.embedding_model_id,
                meta.dimension,
                meta.state,
                meta.updated_at,
            ),
        )


def replace_chunks(network_id: str, node_id: str, chunks: list[RagChunk]) -> None:
    with transaction("workspace") as conn:
        conn.execute(
            "DELETE FROM network_rag_chunks WHERE network_id = ? AND node_id = ?",
            (network_id, node_id),
        )
        for chunk in chunks:
            conn.execute(
                """
                INSERT INTO network_rag_chunks (
                  id, network_id, node_id, source, section, text, file_hash,
                  embedding, embedding_model_id, dimension
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.id,
                    network_id,
                    node_id,
                    chunk.source,
                    chunk.section,
                    chunk.text,
                    chunk.file_hash,
                    pack_f32(chunk.embedding),
                    chunk.embedding_model_id,
                    chunk.dimension,
                ),
            )


def list_chunks(network_id: str, node_id: str) -> list[RagChunk]:
    with locked("workspace") as conn:
        rows = conn.execute(
            """
            SELECT * FROM network_rag_chunks
            WHERE network_id = ? AND node_id = ?
            ORDER BY id
            """,
            (network_id, node_id),
        ).fetchall()
        return [_chunk(row) for row in rows]


def drop_node(network_id: str, node_id: str) -> None:
    with transaction("workspace") as conn:
        conn.execute(
            "DELETE FROM network_rag_chunks WHERE network_id = ? AND node_id = ?",
            (network_id, node_id),
        )
        conn.execute(
            "DELETE FROM network_rag_collections WHERE network_id = ? AND node_id = ?",
            (network_id, node_id),
        )


def drop_network(network_id: str) -> None:
    with transaction("workspace") as conn:
        conn.execute(
            "DELETE FROM network_rag_chunks WHERE network_id = ?", (network_id,)
        )
        conn.execute(
            "DELETE FROM network_rag_collections WHERE network_id = ?", (network_id,)
        )


def list_collection_states(network_id: str) -> list[CollectionMeta]:
    with locked("workspace") as conn:
        rows = conn.execute(
            """
            SELECT * FROM network_rag_collections
            WHERE network_id = ?
            ORDER BY node_id
            """,
            (network_id,),
        ).fetchall()
        return [_collection(row) for row in rows]
