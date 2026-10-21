"""Saved prompts. One row per prompt; tags and body are text."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.db.engine import json_dumps, json_loads, locked, transaction, utc_now
from app.db.errors import NotFound


@dataclass
class PromptRow:
    id: str
    name: str
    description: str | None
    tags: list[str]
    body: str
    created_at: str
    updated_at: str


def _tags(raw: object) -> list[str]:
    loaded = json_loads(raw if isinstance(raw, str) else None, default=[])
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded if str(item).strip()]


def _from_row(row: Any) -> PromptRow:
    return PromptRow(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        tags=_tags(row["tags"]),
        body=row["body"] or "",
        created_at=row["created_at"] or row["updated_at"],
        updated_at=row["updated_at"],
    )


def list_prompts() -> list[PromptRow]:
    with locked("workspace") as conn:
        rows = conn.execute(
            "SELECT * FROM prompts ORDER BY updated_at DESC, name COLLATE NOCASE"
        ).fetchall()
        return [_from_row(row) for row in rows]


def get_prompt(prompt_id: str) -> PromptRow | None:
    with locked("workspace") as conn:
        row = conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()
        return None if row is None else _from_row(row)


def insert_prompt(
    *,
    name: str,
    description: str | None,
    tags: list[str],
    body: str,
    prompt_id: str | None = None,
) -> PromptRow:
    new_id = prompt_id or str(uuid.uuid4())
    now = utc_now()
    with transaction("workspace") as conn:
        conn.execute(
            """
            INSERT INTO prompts (id, name, description, tags, body, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id, name, description, json_dumps(tags), body, now, now),
        )
    row = get_prompt(new_id)
    if row is None:
        raise NotFound("prompts.notFound")
    return row


def update_prompt(
    prompt_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    body: str | None = None,
    touch_description: bool = False,
) -> PromptRow:
    current = get_prompt(prompt_id)
    if current is None:
        raise NotFound("prompts.notFound")
    next_name = current.name if name is None else name
    next_description = current.description if not touch_description and description is None else description
    next_tags = current.tags if tags is None else tags
    next_body = current.body if body is None else body
    with transaction("workspace") as conn:
        conn.execute(
            """
            UPDATE prompts
            SET name = ?, description = ?, tags = ?, body = ?, updated_at = ?
            WHERE id = ?
            """,
            (next_name, next_description, json_dumps(next_tags), next_body, utc_now(), prompt_id),
        )
    row = get_prompt(prompt_id)
    if row is None:
        raise NotFound("prompts.notFound")
    return row


def delete_prompts(ids: list[str]) -> None:
    if not ids:
        return
    with transaction("workspace") as conn:
        conn.executemany("DELETE FROM prompts WHERE id = ?", [(item,) for item in ids])
