"""Schema v1 per store. Callers never CREATE TABLE outside this module."""

from __future__ import annotations

import sqlite3

from app.common.types import StoreId

_SETTINGS_V1 = (
    """
    CREATE TABLE app_settings (
      id INTEGER PRIMARY KEY CHECK (id = 1),
      payload TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE credentials (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      kind TEXT NOT NULL,
      mask TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE mcp_servers (
      id TEXT PRIMARY KEY,
      payload TEXT NOT NULL
    )
    """,
)

_HELP_V1 = (
    """
    CREATE TABLE help_messages (
      id TEXT PRIMARY KEY,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      created_at TEXT NOT NULL,
      sources TEXT
    )
    """,
    """
    CREATE TABLE help_chat_rag_chunks (
      id TEXT PRIMARY KEY,
      source TEXT,
      section TEXT,
      text TEXT NOT NULL,
      file_hash TEXT,
      embedding BLOB,
      embedding_model_id TEXT,
      dimension INTEGER
    )
    """,
)

_WORKSPACE_V1 = (
    """
    CREATE TABLE networks (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      description TEXT,
      tags TEXT NOT NULL DEFAULT '[]',
      document TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      last_used_at TEXT,
      last_run_id TEXT
    )
    """,
    """
    CREATE TABLE network_rag_collections (
      network_id TEXT NOT NULL,
      node_id TEXT NOT NULL,
      source_path TEXT,
      embedding_model_id TEXT,
      dimension INTEGER,
      state TEXT NOT NULL DEFAULT 'missing',
      updated_at TEXT,
      PRIMARY KEY (network_id, node_id),
      FOREIGN KEY (network_id) REFERENCES networks(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE network_rag_chunks (
      id TEXT PRIMARY KEY,
      network_id TEXT NOT NULL,
      node_id TEXT NOT NULL,
      source TEXT,
      section TEXT,
      text TEXT NOT NULL,
      file_hash TEXT,
      embedding BLOB,
      embedding_model_id TEXT,
      dimension INTEGER,
      FOREIGN KEY (network_id, node_id)
        REFERENCES network_rag_collections(network_id, node_id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX idx_nrc_net_node ON network_rag_chunks(network_id, node_id)",
)

_HISTORY_V1 = (
    """
    CREATE TABLE runs (
      id TEXT PRIMARY KEY,
      network_id TEXT NOT NULL,
      network_name TEXT NOT NULL,
      started_at TEXT NOT NULL,
      ended_at TEXT,
      outcome TEXT NOT NULL,
      error_message TEXT,
      error_class TEXT,
      error_node_id TEXT,
      error_node_name TEXT,
      graph_snapshot TEXT,
      chat TEXT,
      models TEXT NOT NULL DEFAULT '[]'
    )
    """,
    """
    CREATE TABLE llm_calls (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      node_id TEXT,
      node_name TEXT,
      provider TEXT NOT NULL,
      model TEXT NOT NULL,
      ok INTEGER NOT NULL,
      duration_ms INTEGER,
      tokens_in INTEGER,
      tokens_out INTEGER,
      error_message TEXT,
      FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE run_logs (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      ts TEXT NOT NULL,
      level TEXT NOT NULL,
      node_id TEXT,
      node_name TEXT,
      message TEXT NOT NULL,
      payload TEXT,
      stack TEXT,
      FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE run_steps (
      run_id TEXT NOT NULL,
      node_id TEXT NOT NULL,
      node_name TEXT,
      role TEXT,
      type TEXT,
      status TEXT,
      wait_reason TEXT,
      error_message TEXT,
      PRIMARY KEY (run_id, node_id),
      FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX idx_runs_started ON runs(started_at)",
    "CREATE INDEX idx_logs_run ON run_logs(run_id, ts)",
    "CREATE INDEX idx_calls_run ON llm_calls(run_id)",
)

V1: dict[StoreId, tuple[str, ...]] = {
    "settings": _SETTINGS_V1,
    "help": _HELP_V1,
    "workspace": _WORKSPACE_V1,
    "history": _HISTORY_V1,
}


def migrate(store: StoreId, conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"
    )
    row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    current = int(row["v"]) if row is not None and row["v"] is not None else 0
    if current < 1:
        conn.execute("BEGIN")
        try:
            for statement in V1[store]:
                conn.execute(statement)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (1)")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        current = 1
    if store == "history" and current < 2:
        conn.execute("BEGIN")
        try:
            conn.execute("ALTER TABLE runs ADD COLUMN updated_at TEXT")
            conn.execute("INSERT INTO schema_migrations (version) VALUES (2)")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
