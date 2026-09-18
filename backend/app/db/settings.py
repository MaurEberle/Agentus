"""app_settings payload = AppSettings camelCase JSON. No secrets."""

from __future__ import annotations

from typing import Any

from app.db.engine import json_dumps, json_loads, locked, transaction


def get_settings() -> dict[str, Any] | None:
    with locked("settings") as conn:
        row = conn.execute("SELECT payload FROM app_settings WHERE id = 1").fetchone()
    if row is None:
        return None
    loaded = json_loads(row["payload"], default=None)
    return loaded if isinstance(loaded, dict) else None


def put_settings(data: dict[str, Any]) -> None:
    payload = json_dumps(data)
    with transaction("settings") as conn:
        conn.execute(
            """
            INSERT INTO app_settings (id, payload) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
            """,
            (payload,),
        )


def list_mcp_servers() -> list[dict[str, Any]]:
    with locked("settings") as conn:
        rows = conn.execute("SELECT id, payload FROM mcp_servers ORDER BY id").fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = json_loads(row["payload"], default={})
        if isinstance(payload, dict):
            items.append({**payload, "id": row["id"]})
        else:
            items.append({"id": row["id"]})
    return items


def get_mcp_server(id: str) -> dict[str, Any] | None:
    with locked("settings") as conn:
        row = conn.execute(
            "SELECT id, payload FROM mcp_servers WHERE id = ?", (id,)
        ).fetchone()
    if row is None:
        return None
    payload = json_loads(row["payload"], default={})
    if isinstance(payload, dict):
        return {**payload, "id": row["id"]}
    return {"id": row["id"]}


def put_mcp_server(id: str, payload: dict[str, Any]) -> None:
    body = json_dumps(payload)
    with transaction("settings") as conn:
        conn.execute(
            """
            INSERT INTO mcp_servers (id, payload) VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
            """,
            (id, body),
        )


def delete_mcp_server(id: str) -> None:
    with transaction("settings") as conn:
        conn.execute("DELETE FROM mcp_servers WHERE id = ?", (id,))
