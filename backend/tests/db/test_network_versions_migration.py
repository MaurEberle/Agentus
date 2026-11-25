"""Migration step 10 gives every existing network a version 1 (fix/netz-versionen/entwurf.md, 13)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.db.migrate import migrate
from app.db.networks import content_hash


def _workspace_at_step_9(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    migrate("workspace", conn)
    # Roll the fresh store back to how step 9 left it.
    conn.execute("DROP TABLE network_versions")
    conn.execute("ALTER TABLE networks DROP COLUMN version")
    conn.execute("ALTER TABLE networks DROP COLUMN revision")
    conn.execute("DELETE FROM schema_migrations WHERE version >= 10")
    return conn


def test_existing_networks_get_version_one(tmp_path: Path) -> None:
    conn = _workspace_at_step_9(tmp_path / "workspace.sqlite")
    document = {"id": "n1", "name": "Alt", "nodes": [], "edges": [], "updatedAt": "2026-01-01T00:00:00Z"}
    conn.execute(
        "INSERT INTO networks (id, name, tags, document, updated_at) VALUES (?, ?, '[]', ?, ?)",
        ("n1", "Alt", json.dumps(document), "2026-01-01T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO networks (id, name, tags, document, updated_at) VALUES (?, ?, '[]', ?, ?)",
        ("n2", "Kaputt", "{not json", "2026-01-02T00:00:00Z"),
    )
    migrate("workspace", conn)
    rows = {row["id"]: row for row in conn.execute("SELECT id, version, revision FROM networks")}
    assert {key: (row["version"], row["revision"]) for key, row in rows.items()} == {"n1": (1, 1), "n2": (1, 1)}
    versions = {
        row["network_id"]: row
        for row in conn.execute("SELECT network_id, version, source, content_hash, created_at FROM network_versions")
    }
    assert set(versions) == {"n1", "n2"}
    assert versions["n1"]["source"] == "migration"
    assert versions["n1"]["content_hash"] == content_hash(document)
    assert versions["n1"]["created_at"] == "2026-01-01T00:00:00Z"
    migrate("workspace", conn)  # idempotent
    assert conn.execute("SELECT COUNT(*) FROM network_versions").fetchone()[0] == 2
    conn.close()
