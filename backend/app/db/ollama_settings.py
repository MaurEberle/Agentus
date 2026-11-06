"""Read-only peek into Ollama's own settings DB (not one of our stores)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def read_models_dir(db_path: Path) -> str | None:
    """Return Ollama's configured models directory, or None when unset or unreadable."""
    try:
        uri = db_path.resolve().as_posix()
        conn = sqlite3.connect(f"file:{uri}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT models FROM settings LIMIT 1").fetchone()
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        return None
    value = str(row[0]).strip() if row and row[0] is not None else ""
    return value or None
