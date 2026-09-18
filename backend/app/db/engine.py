"""One sqlite connection per store, lock per store. No SQL in callers."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.common.types import STORE_IDS, StoreId
from app.db.errors import StoreUnavailable
from app.db.paths import RAG_DIR_NAME

_locks: dict[StoreId, threading.Lock] = {store: threading.Lock() for store in STORE_IDS}
_conns: dict[StoreId, sqlite3.Connection] = {}
_states: dict[StoreId, str] = {}
_bootstrap: Any = None


def json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def json_loads(text: str | None, default: Any = None) -> Any:
    if text is None:
        return default
    return json.loads(text)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_bootstrap(bootstrap: Any) -> None:
    global _bootstrap
    _bootstrap = bootstrap


def get_bootstrap() -> Any:
    if _bootstrap is None:
        raise StoreUnavailable("store.missing")
    return _bootstrap


def db_path(store: StoreId) -> Path:
    bootstrap = get_bootstrap()
    return Path(bootstrap.data_dir) / getattr(bootstrap.stores, store)


def store_state(store: StoreId) -> str:
    return _states.get(store, "missing")


def store_statuses() -> list[dict[str, Any]]:
    bootstrap = get_bootstrap()
    items: list[dict[str, Any]] = []
    for store in STORE_IDS:
        state = _states.get(store, "missing")
        item: dict[str, Any] = {
            "id": store,
            "fileName": getattr(bootstrap.stores, store),
            "ok": state == "ok",
            "state": state,
        }
        if state == "missing":
            item["messageKey"] = "store.missing"
        elif state == "error":
            item["messageKey"] = "store.error"
        items.append(item)
    return items


def _connect_file(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def require_conn(store: StoreId) -> sqlite3.Connection:
    state = _states.get(store, "missing")
    conn = _conns.get(store)
    if conn is None or state != "ok":
        if state == "error":
            raise StoreUnavailable("store.error", store_id=store)
        raise StoreUnavailable("store.missing", store_id=store)
    return conn


@contextmanager
def locked(store: StoreId) -> Iterator[sqlite3.Connection]:
    conn = require_conn(store)
    with _locks[store]:
        yield conn


@contextmanager
def transaction(store: StoreId) -> Iterator[sqlite3.Connection]:
    conn = require_conn(store)
    with _locks[store]:
        conn.execute("BEGIN")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def connect(store: StoreId) -> sqlite3.Connection:
    """Return the cached connection (after ``open_all``)."""
    return require_conn(store)


def open_all() -> None:
    from app.db.migrate import migrate

    bootstrap = get_bootstrap()
    data_dir = Path(bootstrap.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / RAG_DIR_NAME).mkdir(parents=True, exist_ok=True)

    for store in STORE_IDS:
        path = db_path(store)
        existing = _conns.pop(store, None)
        if existing is not None:
            try:
                existing.close()
            except sqlite3.Error:
                pass
        try:
            conn = _connect_file(path)
            migrate(store, conn)
            _conns[store] = conn
            _states[store] = "ok"
        except sqlite3.Error:
            _states[store] = "error"
            _conns.pop(store, None)
        except OSError:
            _states[store] = "missing" if not path.exists() else "error"
            _conns.pop(store, None)


def close_store(store: StoreId, *, state: str = "missing") -> None:
    conn = _conns.pop(store, None)
    if conn is not None:
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except sqlite3.Error:
            pass
    _states[store] = state


def close_all() -> None:
    for store in STORE_IDS:
        close_store(store, state="missing")


def reset() -> None:
    close_all()
    _states.clear()
    global _bootstrap
    _bootstrap = None
