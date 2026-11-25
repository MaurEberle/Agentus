"""Architect sessions and their chat in the workspace store (fix/netz-architekt/entwurf.md, 10)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.db.engine import json_dumps, json_loads, locked, transaction

# Session columns that hold JSON.
_JSON_COLUMNS = ("brief", "draft", "ids", "source", "applied", "proposal", "counters")
_COLUMNS = (
    "id",
    "title",
    "provider",
    "model",
    "credential_id",
    "catalog_hash",
    "state",
    "brief",
    "draft",
    "ids",
    "source",
    "applied",
    "proposal",
    "counters",
    "created_at",
    "updated_at",
    "last_input_at",
)


@dataclass
class ArchitectSessionRow:
    id: str
    title: str
    provider: str
    model: str
    credential_id: str | None
    catalog_hash: str
    state: str
    created_at: str
    updated_at: str
    brief: dict[str, Any] = field(default_factory=dict)
    draft: dict[str, Any] | None = None
    # ref -> node id, so ids stay stable while the draft changes.
    ids: dict[str, str] = field(default_factory=dict)
    # A network read in to change it: networkId, version, revision, refs.
    source: dict[str, Any] | None = None
    applied: list[dict[str, Any]] = field(default_factory=list)
    proposal: dict[str, Any] | None = None
    counters: dict[str, int] = field(default_factory=dict)
    last_input_at: str | None = None


@dataclass
class ArchitectMessageRow:
    id: str
    session_id: str
    role: str
    content: str
    created_at: str
    tools: list[dict[str, Any]] | None = None


_LIST_COLUMNS = frozenset({"applied"})


def _session(row: Any) -> ArchitectSessionRow:
    def loads(name: str, default: Any) -> Any:
        if row[name] is None:
            return default
        value = json_loads(row[name], default=default)
        expected = list if name in _LIST_COLUMNS else dict
        return value if isinstance(value, expected) else default

    return ArchitectSessionRow(
        id=row["id"],
        title=row["title"] or "",
        provider=row["provider"],
        model=row["model"],
        credential_id=row["credential_id"],
        catalog_hash=row["catalog_hash"] or "",
        state=row["state"] or "ended",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        brief=loads("brief", {}),
        draft=loads("draft", None),
        ids=loads("ids", {}),
        source=loads("source", None),
        applied=loads("applied", []),
        proposal=loads("proposal", None),
        counters=loads("counters", {}),
        last_input_at=row["last_input_at"],
    )


def _values(row: ArchitectSessionRow) -> tuple[Any, ...]:
    out: list[Any] = []
    for name in _COLUMNS:
        value = getattr(row, name)
        out.append(json_dumps(value) if name in _JSON_COLUMNS and value is not None else value)
    return tuple(out)


def insert_session(row: ArchitectSessionRow) -> None:
    marks = ", ".join("?" for _ in _COLUMNS)
    with transaction("workspace") as conn:
        conn.execute(f"INSERT INTO architect_sessions ({', '.join(_COLUMNS)}) VALUES ({marks})", _values(row))


def save_session(row: ArchitectSessionRow) -> None:
    sets = ", ".join(f"{name} = ?" for name in _COLUMNS[1:])
    values = _values(row)
    with transaction("workspace") as conn:
        conn.execute(f"UPDATE architect_sessions SET {sets} WHERE id = ?", (*values[1:], values[0]))


def get_session(session_id: str) -> ArchitectSessionRow | None:
    with locked("workspace") as conn:
        row = conn.execute("SELECT * FROM architect_sessions WHERE id = ?", (session_id,)).fetchone()
        return _session(row) if row is not None else None


def list_sessions() -> list[ArchitectSessionRow]:
    with locked("workspace") as conn:
        rows = conn.execute("SELECT * FROM architect_sessions ORDER BY updated_at DESC, id DESC").fetchall()
        return [_session(row) for row in rows]


def end_active_sessions() -> None:
    """After a crash or restart nothing is running any more."""
    with transaction("workspace") as conn:
        conn.execute("UPDATE architect_sessions SET state = 'ended' WHERE state = 'active'")


def delete_session(session_id: str) -> None:
    with transaction("workspace") as conn:
        conn.execute("DELETE FROM architect_messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM architect_sessions WHERE id = ?", (session_id,))


def _message(row: Any) -> ArchitectMessageRow:
    tools = json_loads(row["tools"], default=None) if row["tools"] is not None else None
    return ArchitectMessageRow(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
        tools=tools if isinstance(tools, list) else None,
    )


def insert_message(row: ArchitectMessageRow) -> None:
    with transaction("workspace") as conn:
        conn.execute(
            """
            INSERT INTO architect_messages (id, session_id, role, content, tools, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (row.id, row.session_id, row.role, row.content, json_dumps(row.tools) if row.tools else None, row.created_at),
        )


def message_counts() -> dict[str, int]:
    """Messages per session, in one query for the session list."""
    with locked("workspace") as conn:
        rows = conn.execute("SELECT session_id, COUNT(*) AS n FROM architect_messages GROUP BY session_id").fetchall()
        return {str(row["session_id"]): int(row["n"]) for row in rows}


def list_messages(session_id: str) -> list[ArchitectMessageRow]:
    with locked("workspace") as conn:
        rows = conn.execute(
            "SELECT * FROM architect_messages WHERE session_id = ? ORDER BY created_at ASC, id ASC",
            (session_id,),
        ).fetchall()
        return [_message(row) for row in rows]
