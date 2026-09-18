"""Workspace networks. Delete + RAG is one workspace TX; history is untouched."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.db.engine import json_dumps, json_loads, locked, transaction, utc_now
from app.db.errors import NotFound


@dataclass
class NetworkRow:
    id: str
    name: str
    description: str | None
    tags: list[str]
    document: dict[str, Any]
    updated_at: str
    last_used_at: str | None
    last_run_id: str | None


def _tags(raw: object) -> list[str]:
    loaded = json_loads(raw if isinstance(raw, str) else None, default=[])
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _document(raw: str) -> dict[str, Any]:
    loaded = json_loads(raw, default={})
    return loaded if isinstance(loaded, dict) else {}


def _from_row(row: Any) -> NetworkRow:
    return NetworkRow(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        tags=_tags(row["tags"]),
        document=_document(row["document"]),
        updated_at=row["updated_at"],
        last_used_at=row["last_used_at"],
        last_run_id=row["last_run_id"],
    )


def _fetch(conn: Any, network_id: str) -> NetworkRow | None:
    row = conn.execute("SELECT * FROM networks WHERE id = ?", (network_id,)).fetchone()
    return None if row is None else _from_row(row)


def list_networks() -> list[NetworkRow]:
    with locked("workspace") as conn:
        rows = conn.execute(
            "SELECT * FROM networks ORDER BY updated_at DESC, name COLLATE NOCASE"
        ).fetchall()
        return [_from_row(row) for row in rows]


def get_network(id: str) -> NetworkRow | None:
    with locked("workspace") as conn:
        return _fetch(conn, id)


def upsert_network(row: NetworkRow) -> None:
    # ON CONFLICT UPDATE — not REPLACE — so RAG rows survive.
    with transaction("workspace") as conn:
        conn.execute(
            """
            INSERT INTO networks (
              id, name, description, tags, document, updated_at, last_used_at, last_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name,
              description = excluded.description,
              tags = excluded.tags,
              document = excluded.document,
              updated_at = excluded.updated_at,
              last_used_at = excluded.last_used_at,
              last_run_id = excluded.last_run_id
            """,
            (
                row.id,
                row.name,
                row.description,
                json_dumps(row.tags),
                json_dumps(row.document),
                row.updated_at,
                row.last_used_at,
                row.last_run_id,
            ),
        )


def touch_network(
    id: str, *, last_used_at: str | None = None, last_run_id: str | None = None
) -> None:
    fields: list[str] = []
    params: list[object] = []
    if last_used_at is not None:
        fields.append("last_used_at = ?")
        params.append(last_used_at)
    if last_run_id is not None:
        fields.append("last_run_id = ?")
        params.append(last_run_id)
    if not fields:
        return
    params.append(id)
    with transaction("workspace") as conn:
        cur = conn.execute(
            f"UPDATE networks SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        if cur.rowcount == 0:
            raise NotFound("db.notFound", store_id="workspace")


def delete_network(id: str) -> None:
    with transaction("workspace") as conn:
        cur = conn.execute("DELETE FROM networks WHERE id = ?", (id,))
        if cur.rowcount == 0:
            raise NotFound("db.notFound", store_id="workspace")


def duplicate_network(id: str, new_id: str, new_name: str) -> NetworkRow:
    with transaction("workspace") as conn:
        src = _fetch(conn, id)
        if src is None:
            raise NotFound("db.notFound", store_id="workspace")
        document = dict(src.document)
        document["id"] = new_id
        now = utc_now()
        conn.execute(
            """
            INSERT INTO networks (
              id, name, description, tags, document, updated_at, last_used_at, last_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                new_id,
                new_name,
                src.description,
                json_dumps(src.tags),
                json_dumps(document),
                now,
            ),
        )
        collections = conn.execute(
            """
            SELECT node_id, source_path, embedding_model_id, dimension, state, updated_at
            FROM network_rag_collections WHERE network_id = ?
            """,
            (id,),
        ).fetchall()
        for col in collections:
            conn.execute(
                """
                INSERT INTO network_rag_collections (
                  network_id, node_id, source_path, embedding_model_id,
                  dimension, state, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    col["node_id"],
                    col["source_path"],
                    col["embedding_model_id"],
                    col["dimension"],
                    col["state"],
                    col["updated_at"],
                ),
            )
        chunks = conn.execute(
            "SELECT * FROM network_rag_chunks WHERE network_id = ?",
            (id,),
        ).fetchall()
        for chunk in chunks:
            conn.execute(
                """
                INSERT INTO network_rag_chunks (
                  id, network_id, node_id, source, section, text, file_hash,
                  embedding, embedding_model_id, dimension
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    new_id,
                    chunk["node_id"],
                    chunk["source"],
                    chunk["section"],
                    chunk["text"],
                    chunk["file_hash"],
                    chunk["embedding"],
                    chunk["embedding_model_id"],
                    chunk["dimension"],
                ),
            )
        copied = _fetch(conn, new_id)
        assert copied is not None
        return copied
