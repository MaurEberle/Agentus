"""Credential metadata only. Secrets live in vault. Keys: snake_case."""

from __future__ import annotations

from typing import Any

from app.db.engine import locked, transaction, utc_now
from app.db.errors import NotFound


def _row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "kind": row["kind"],
        "mask": row["mask"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_credentials() -> list[dict[str, Any]]:
    with locked("settings") as conn:
        rows = conn.execute(
            """
            SELECT id, name, kind, mask, created_at, updated_at
            FROM credentials
            ORDER BY name COLLATE NOCASE, id
            """
        ).fetchall()
    return [_row(row) for row in rows]


def get_credential(id: str) -> dict[str, Any] | None:
    with locked("settings") as conn:
        row = conn.execute(
            """
            SELECT id, name, kind, mask, created_at, updated_at
            FROM credentials WHERE id = ?
            """,
            (id,),
        ).fetchone()
    return None if row is None else _row(row)


def insert_credential(id: str, name: str, kind: str, mask: str) -> None:
    now = utc_now()
    with transaction("settings") as conn:
        conn.execute(
            """
            INSERT INTO credentials (id, name, kind, mask, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (id, name, kind, mask, now, now),
        )


def update_credential_meta(
    id: str,
    name: str | None = None,
    kind: str | None = None,
    mask: str | None = None,
) -> None:
    with transaction("settings") as conn:
        row = conn.execute("SELECT id FROM credentials WHERE id = ?", (id,)).fetchone()
        if row is None:
            raise NotFound("db.notFound", store_id="settings")
        fields: list[str] = []
        params: list[object] = []
        if name is not None:
            fields.append("name = ?")
            params.append(name)
        if kind is not None:
            fields.append("kind = ?")
            params.append(kind)
        if mask is not None:
            fields.append("mask = ?")
            params.append(mask)
        if not fields:
            return
        fields.append("updated_at = ?")
        params.append(utc_now())
        params.append(id)
        conn.execute(
            f"UPDATE credentials SET {', '.join(fields)} WHERE id = ?",
            params,
        )


def delete_credential_meta(id: str) -> None:
    with transaction("settings") as conn:
        cur = conn.execute("DELETE FROM credentials WHERE id = ?", (id,))
        if cur.rowcount == 0:
            raise NotFound("db.notFound", store_id="settings")
