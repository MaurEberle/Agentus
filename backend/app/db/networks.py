"""Workspace networks. Delete + RAG is one workspace TX; history is untouched."""

from __future__ import annotations

import hashlib
import json
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
    version: int = 1
    revision: int = 1


def _tags(raw: object) -> list[str]:
    loaded = json_loads(raw if isinstance(raw, str) else None, default=[])
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _document(raw: str) -> dict[str, Any]:
    loaded = json_loads(raw, default={})
    return loaded if isinstance(loaded, dict) else {}


def _from_row(row: Any) -> NetworkRow:
    keys = set(row.keys())
    return NetworkRow(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        tags=_tags(row["tags"]),
        document=_document(row["document"]),
        updated_at=row["updated_at"],
        last_used_at=row["last_used_at"],
        last_run_id=row["last_run_id"],
        version=int(row["version"]) if "version" in keys and row["version"] is not None else 1,
        revision=int(row["revision"]) if "revision" in keys and row["revision"] is not None else 1,
    )


# --- versions (fix/netz-versionen/entwurf.md) ----------------------------------------------

# Fields that change without the network changing: time stamps, view, server additions.
_VOLATILE = ("updatedAt", "viewport", "id", "knowledge", "version", "revision")
DEFAULT_KEEP = 50


class VersionConflict(Exception):
    """The network changed since the caller read it (another writer)."""

    def __init__(self, version: int, revision: int) -> None:
        self.version = version
        self.revision = revision
        super().__init__("networks.conflict")


def content_hash(document: dict[str, Any]) -> str:
    """Fingerprint of what a network is, without time stamps and the view."""
    clean = {key: value for key, value in document.items() if key not in _VOLATILE}
    raw = json.dumps(clean, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _insert_version(
    conn: Any,
    network_id: str,
    version: int,
    document: dict[str, Any],
    *,
    source: str,
    note: str | None,
    restored_from: int | None = None,
) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO network_versions (
          network_id, version, document, content_hash, created_at, updated_at, source, note, pinned, restored_from
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (network_id, version, json_dumps(document), content_hash(document), now, now, source, note, restored_from),
    )


def _prune(conn: Any, network_id: str, current: int, keep: int) -> None:
    """Keep the newest ``keep`` versions plus version 1, pinned ones and the current one."""
    rows = conn.execute(
        "SELECT version, pinned FROM network_versions WHERE network_id = ? ORDER BY version DESC",
        (network_id,),
    ).fetchall()
    protected = {int(row["version"]) for row in rows[: max(1, keep)]} | {1, current}
    protected |= {int(row["version"]) for row in rows if row["pinned"]}
    for row in rows:
        if int(row["version"]) not in protected:
            conn.execute(
                "DELETE FROM network_versions WHERE network_id = ? AND version = ?",
                (network_id, int(row["version"])),
            )


def write_versioned(
    row: NetworkRow,
    *,
    mode: str = "current",
    source: str = "editor",
    note: str | None = None,
    keep: int = DEFAULT_KEEP,
    base_revision: int | None = None,
    restored_from: int | None = None,
) -> NetworkRow:
    """Write a network and its version in one transaction.

    ``mode``: ``new`` starts a new version unless the content is unchanged; ``current``
    writes into the current version. A network that does not exist yet starts at version 1.
    Every write raises the revision; a stale ``base_revision`` raises VersionConflict.
    """
    with transaction("workspace") as conn:
        current = conn.execute("SELECT version, revision FROM networks WHERE id = ?", (row.id,)).fetchone()
        if current is None:
            version, revision = 1, 1
            conn.execute(
                """
                INSERT INTO networks (
                  id, name, description, tags, document, updated_at, last_used_at, last_run_id, version, revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1)
                """,
                (row.id, row.name, row.description, json_dumps(row.tags), json_dumps(row.document),
                 row.updated_at, row.last_used_at, row.last_run_id),
            )
            _insert_version(conn, row.id, 1, row.document, source=source, note=note, restored_from=restored_from)
        else:
            if base_revision is not None and int(current["revision"]) != base_revision:
                raise VersionConflict(int(current["version"]), int(current["revision"]))
            version = int(current["version"])
            revision = int(current["revision"]) + 1
            stored = conn.execute(
                "SELECT content_hash FROM network_versions WHERE network_id = ? AND version = ?",
                (row.id, version),
            ).fetchone()
            changed = stored is None or stored["content_hash"] != content_hash(row.document)
            if mode == "new" and changed and stored is not None:
                top = conn.execute(
                    "SELECT MAX(version) AS v FROM network_versions WHERE network_id = ?", (row.id,)
                ).fetchone()
                version = int(top["v"] or version) + 1
                _insert_version(conn, row.id, version, row.document, source=source, note=note, restored_from=restored_from)
            elif stored is None:
                _insert_version(conn, row.id, version, row.document, source=source, note=note, restored_from=restored_from)
            else:
                conn.execute(
                    """
                    UPDATE network_versions
                    SET document = ?, content_hash = ?, updated_at = ?, note = COALESCE(?, note)
                    WHERE network_id = ? AND version = ?
                    """,
                    (json_dumps(row.document), content_hash(row.document), utc_now(), note, row.id, version),
                )
            conn.execute(
                """
                UPDATE networks SET
                  name = ?, description = ?, tags = ?, document = ?, updated_at = ?,
                  last_used_at = ?, last_run_id = ?, version = ?, revision = ?
                WHERE id = ?
                """,
                (row.name, row.description, json_dumps(row.tags), json_dumps(row.document), row.updated_at,
                 row.last_used_at, row.last_run_id, version, revision, row.id),
            )
        _prune(conn, row.id, version, keep)
    row.version, row.revision = version, revision
    return row


def _version_row(row: Any, *, with_document: bool) -> dict[str, Any]:
    document = _document(row["document"])
    out: dict[str, Any] = {
        "version": int(row["version"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "source": row["source"],
        "note": row["note"],
        "pinned": bool(row["pinned"]),
        "restoredFrom": row["restored_from"],
        "nodeCount": len(document.get("nodes") or []),
        "contentHash": row["content_hash"],
    }
    if with_document:
        out["document"] = document
    return out


def list_versions(network_id: str) -> list[dict[str, Any]]:
    with locked("workspace") as conn:
        rows = conn.execute(
            "SELECT * FROM network_versions WHERE network_id = ? ORDER BY version DESC", (network_id,)
        ).fetchall()
        return [_version_row(row, with_document=False) for row in rows]


def get_version(network_id: str, version: int) -> dict[str, Any] | None:
    with locked("workspace") as conn:
        row = conn.execute(
            "SELECT * FROM network_versions WHERE network_id = ? AND version = ?", (network_id, version)
        ).fetchone()
        return _version_row(row, with_document=True) if row is not None else None


def version_for_hash(network_id: str, digest: str) -> int | None:
    """The newest kept version with this content (a run's snapshot, entwurf.md 12)."""
    with locked("workspace") as conn:
        row = conn.execute(
            "SELECT MAX(version) AS v FROM network_versions WHERE network_id = ? AND content_hash = ?",
            (network_id, digest),
        ).fetchone()
        return int(row["v"]) if row is not None and row["v"] is not None else None


def set_version_meta(network_id: str, version: int, *, pinned: bool | None = None, note: str | None = None) -> bool:
    fields: list[str] = []
    params: list[object] = []
    if pinned is not None:
        fields.append("pinned = ?")
        params.append(1 if pinned else 0)
    if note is not None:
        fields.append("note = ?")
        params.append(note or None)
    if not fields:
        return True
    params += [network_id, version]
    with transaction("workspace") as conn:
        cur = conn.execute(
            f"UPDATE network_versions SET {', '.join(fields)} WHERE network_id = ? AND version = ?", params
        )
        return cur.rowcount > 0


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
    """Write a network into its current version (version 1 when new). UPDATE, not REPLACE, so RAG rows survive."""
    write_versioned(row, mode="current", source="create")


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
    """V-5: no bin; the versions go with the network."""
    with transaction("workspace") as conn:
        cur = conn.execute("DELETE FROM networks WHERE id = ?", (id,))
        if cur.rowcount == 0:
            raise NotFound("db.notFound", store_id="workspace")
        conn.execute("DELETE FROM network_versions WHERE network_id = ?", (id,))


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
        # The copy starts its own history at version 1; the note names where it came from.
        _insert_version(conn, new_id, 1, document, source="duplicate", note=f"{src.name} · {src.version}")
        collections = conn.execute(
            """
            SELECT node_id, source_path, embedding_model_id, dimension, state, updated_at,
                   content_fingerprint
            FROM network_rag_collections WHERE network_id = ?
            """,
            (id,),
        ).fetchall()
        for col in collections:
            conn.execute(
                """
                INSERT INTO network_rag_collections (
                  network_id, node_id, source_path, embedding_model_id,
                  dimension, state, updated_at, content_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    col["node_id"],
                    col["source_path"],
                    col["embedding_model_id"],
                    col["dimension"],
                    col["state"],
                    col["updated_at"],
                    col["content_fingerprint"],
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
