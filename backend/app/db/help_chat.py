"""Help chat transcript in the help store. Not workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.engine import json_dumps, json_loads, locked, transaction


@dataclass
class HelpMessageRow:
    id: str
    role: str
    content: str
    created_at: str
    sources: list[Any] | None


def _from_row(row: Any) -> HelpMessageRow:
    sources = json_loads(row["sources"], default=None) if row["sources"] is not None else None
    if sources is not None and not isinstance(sources, list):
        sources = None
    return HelpMessageRow(
        id=row["id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
        sources=sources,
    )


def list_messages() -> list[HelpMessageRow]:
    with locked("help") as conn:
        rows = conn.execute(
            "SELECT * FROM help_messages ORDER BY created_at ASC, id ASC"
        ).fetchall()
        return [_from_row(row) for row in rows]


def insert_message(row: HelpMessageRow) -> None:
    sources = json_dumps(row.sources) if row.sources is not None else None
    with transaction("help") as conn:
        conn.execute(
            """
            INSERT INTO help_messages (id, role, content, created_at, sources)
            VALUES (?, ?, ?, ?, ?)
            """,
            (row.id, row.role, row.content, row.created_at, sources),
        )


def clear_messages() -> None:
    with transaction("help") as conn:
        conn.execute("DELETE FROM help_messages")
