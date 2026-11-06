"""One-at-a-time Hugging Face pulls. The queue survives a restart."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections import deque
from typing import Any

from pydantic import Field

from app.common.http import client
from app.db.engine import json_dumps, locked, transaction, utc_now
from app.http.app import ApiModel
from app.llm.blobs import discard_blob_files, fetch_manifest_digests, stored_digests
from app.llm.hub import valid_pull_model
from app.llm.pull import pull_events
from app.llm.usage import model_usages
from app.runtime.errors import RuntimeApiError
from app.runtime.ollama import resident_index, tag_key
from app.runtime.urls import ollama_native_root, settings_roots

log = logging.getLogger("agentus.downloads")

_LOCK = threading.Lock()
_CANCEL = threading.Event()
_THREAD: threading.Thread | None = None
_PROGRESS: dict[str, dict[str, int | float]] = {}
_SAMPLES: deque[tuple[float, int]] = deque()


class DownloadJob(ApiModel):
    id: str
    model: str
    label: str
    publisher: str | None = None
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    status: str
    error_key: str | None = Field(default=None, alias="errorKey")
    completed: int | None = None
    total: int | None = None
    rate_bps: int | None = Field(default=None, alias="rateBps")


class DownloadList(ApiModel):
    paused: bool = False
    items: list[DownloadJob] = Field(default_factory=list)


class DownloadCreate(ApiModel):
    model: str
    label: str = ""
    publisher: str | None = None
    size_bytes: int | None = Field(default=None, alias="sizeBytes")


class DownloadIds(ApiModel):
    ids: list[str] = Field(default_factory=list)


def _row_job(row: Any) -> DownloadJob:
    progress = _PROGRESS.get(str(row["id"]), {})
    completed = progress.get("completed")
    total = progress.get("total")
    rate = progress.get("rate")
    return DownloadJob(
        id=str(row["id"]),
        model=str(row["model"]),
        label=str(row["label"]),
        publisher=str(row["publisher"]) if row["publisher"] else None,
        size_bytes=int(row["size_bytes"]) if isinstance(row["size_bytes"], int) else None,
        status=str(row["status"]),
        error_key=str(row["error_key"]) if row["error_key"] else None,
        completed=int(completed) if isinstance(completed, (int, float)) else None,
        total=int(total) if isinstance(total, (int, float)) else None,
        rate_bps=int(rate) if isinstance(rate, (int, float)) and rate > 0 else None,
    )


def _gate_paused(conn: Any) -> bool:
    row = conn.execute("SELECT paused FROM download_gate WHERE id = 1").fetchone()
    return bool(row and int(row["paused"]))


def list_downloads() -> DownloadList:
    with locked("workspace") as conn:
        paused = _gate_paused(conn)
        rows = conn.execute(
            """
            SELECT * FROM model_downloads
            ORDER BY
              CASE status
                WHEN 'running' THEN 0
                WHEN 'queued' THEN 1
                WHEN 'paused' THEN 2
                WHEN 'error' THEN 3
                WHEN 'stopped' THEN 4
                ELSE 5
              END,
              position ASC,
              created_at ASC
            """
        ).fetchall()
    return DownloadList(paused=paused, items=[_row_job(row) for row in rows])


def _next_position(conn: Any) -> int:
    row = conn.execute("SELECT COALESCE(MAX(position), 0) AS n FROM model_downloads").fetchone()
    return int(row["n"]) + 1


def _front_position(conn: Any) -> int:
    row = conn.execute("SELECT COALESCE(MIN(position), 1) AS n FROM model_downloads").fetchone()
    return int(row["n"]) - 1


def enqueue(body: DownloadCreate) -> DownloadList:
    model = body.model.strip()
    if not valid_pull_model(model):
        raise RuntimeApiError("models.pull.invalid")
    label = body.label.strip() or model
    now = utc_now()
    with transaction("workspace") as conn:
        existing = conn.execute(
            "SELECT id FROM model_downloads WHERE model = ? AND status IN ('queued', 'running', 'paused')",
            (model,),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO model_downloads (
                  id, model, label, publisher, size_bytes, status, position, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    model,
                    label[:180],
                    (body.publisher or "").strip() or None,
                    body.size_bytes if isinstance(body.size_bytes, int) and body.size_bytes > 0 else None,
                    _next_position(conn),
                    now,
                    now,
                ),
            )
    ensure_worker()
    return list_downloads()


def _set_status(conn: Any, download_id: str, status: str, *, front: bool = False) -> None:
    position = _front_position(conn) if front else None
    if position is None:
        conn.execute(
            "UPDATE model_downloads SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now(), download_id),
        )
        return
    conn.execute(
        "UPDATE model_downloads SET status = ?, position = ?, updated_at = ? WHERE id = ?",
        (status, position, utc_now(), download_id),
    )


def _running_id(conn: Any) -> str | None:
    row = conn.execute("SELECT id FROM model_downloads WHERE status = 'running' LIMIT 1").fetchone()
    return str(row["id"]) if row else None


def pause_all() -> DownloadList:
    with transaction("workspace") as conn:
        conn.execute("UPDATE download_gate SET paused = 1 WHERE id = 1")
        running = _running_id(conn)
        if running:
            _set_status(conn, running, "queued", front=True)
    _CANCEL.set()
    return list_downloads()


def resume_all() -> DownloadList:
    """Open the gate and put paused rows back in line. The first one starts."""
    with transaction("workspace") as conn:
        conn.execute("UPDATE download_gate SET paused = 0 WHERE id = 1")
        conn.execute(
            "UPDATE model_downloads SET status = 'queued', updated_at = ? WHERE status = 'paused'",
            (utc_now(),),
        )
    ensure_worker()
    return list_downloads()


def pause_one(download_id: str) -> DownloadList:
    with transaction("workspace") as conn:
        row = conn.execute("SELECT status FROM model_downloads WHERE id = ?", (download_id,)).fetchone()
        if row and row["status"] in {"running", "queued"}:
            _set_status(conn, download_id, "paused")
            if row["status"] == "running":
                _CANCEL.set()
    return list_downloads()


def resume_one(download_id: str) -> DownloadList:
    with transaction("workspace") as conn:
        row = conn.execute("SELECT status FROM model_downloads WHERE id = ?", (download_id,)).fetchone()
        if row and row["status"] in {"paused", "stopped", "error"}:
            _set_status(conn, download_id, "queued", front=True)
    ensure_worker()
    return list_downloads()


def stop_one(download_id: str) -> DownloadList:
    with transaction("workspace") as conn:
        row = conn.execute("SELECT status FROM model_downloads WHERE id = ?", (download_id,)).fetchone()
        if row and row["status"] in {"running", "queued", "paused"}:
            _set_status(conn, download_id, "stopped")
            if row["status"] == "running":
                _CANCEL.set()
    return list_downloads()


def _save_digests(download_id: str, digests: set[str]) -> None:
    with transaction("workspace") as conn:
        conn.execute(
            "UPDATE model_downloads SET digests = ?, updated_at = ? WHERE id = ?",
            (json_dumps(sorted(digests)), utc_now(), download_id),
        )


def _forget_installed(model: str) -> None:
    if model_usages(model) or tag_key(model) in resident_index():
        return
    root = settings_roots()[0] or ollama_native_root("")
    if not root:
        return
    try:
        with client(timeout_sec=120.0) as http:
            response = http.request("DELETE", f"{root}/api/delete", json={"model": model})
        if response.status_code not in {200, 404}:
            return
    except Exception:
        return


def _discard(model: str, remembered: list[str]) -> None:
    digests = list(dict.fromkeys([*remembered, *fetch_manifest_digests(model)]))
    _forget_installed(model)
    discard_blob_files(digests)


def remove_downloads(ids: list[str]) -> DownloadList:
    clean = [item.strip() for item in ids if item.strip()]
    if not clean:
        return list_downloads()
    with transaction("workspace") as conn:
        marks = ",".join("?" for _ in clean)
        rows = conn.execute(
            f"SELECT id, model, digests, status FROM model_downloads WHERE id IN ({marks})",
            clean,
        ).fetchall()
        running = _running_id(conn)
        if running and running in clean:
            _set_status(conn, running, "stopped")
            _CANCEL.set()
        conn.execute(f"DELETE FROM model_downloads WHERE id IN ({marks})", clean)
    cancelled = any(row["status"] == "running" for row in rows)
    if cancelled:
        time.sleep(0.4)
    for row in rows:
        if row["status"] == "done":
            continue
        remembered = stored_digests(str(row["digests"]) if row["digests"] is not None else "[]")
        _discard(str(row["model"]), remembered)
    return list_downloads()


def recover_after_restart() -> None:
    """A kill mid-pull leaves status running. A paused gate keeps that job queued."""
    with transaction("workspace") as conn:
        running = _running_id(conn)
        if not running:
            return
        if _gate_paused(conn):
            _set_status(conn, running, "queued", front=True)


def _claim() -> Any | None:
    with transaction("workspace") as conn:
        if _gate_paused(conn):
            return None
        row = conn.execute(
            "SELECT * FROM model_downloads WHERE status = 'running' ORDER BY position ASC LIMIT 1"
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT * FROM model_downloads WHERE status = 'queued' ORDER BY position ASC, created_at ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE model_downloads SET status = 'running', updated_at = ? WHERE id = ?",
                (utc_now(), row["id"]),
            )
        return row


def _finish(download_id: str, status: str, error_key: str | None = None) -> None:
    with transaction("workspace") as conn:
        current = conn.execute("SELECT status FROM model_downloads WHERE id = ?", (download_id,)).fetchone()
        if current is None or current["status"] != "running":
            return
        conn.execute(
            "UPDATE model_downloads SET status = ?, error_key = ?, updated_at = ? WHERE id = ?",
            (status, error_key, utc_now(), download_id),
        )
    _PROGRESS.pop(download_id, None)


def _note_progress(download_id: str, completed: int | None, total: int | None) -> None:
    now = time.monotonic()
    if completed is None:
        return
    if _SAMPLES and completed < _SAMPLES[-1][1]:
        _SAMPLES.clear()
    _SAMPLES.append((now, completed))
    while _SAMPLES and now - _SAMPLES[0][0] > 4:
        _SAMPLES.popleft()
    rate = 0.0
    if len(_SAMPLES) >= 2:
        span = _SAMPLES[-1][0] - _SAMPLES[0][0]
        delta = _SAMPLES[-1][1] - _SAMPLES[0][1]
        if span > 0.2 and delta >= 0:
            rate = delta / span
    _PROGRESS[download_id] = {"completed": completed, "total": total or 0, "rate": rate}


def _loop() -> None:
    while True:
        try:
            row = _claim()
        except Exception:
            # Store closed or busy (e.g. data-dir switch): back off, never let the worker die.
            log.warning("download queue unavailable; retrying", exc_info=True)
            time.sleep(2.0)
            continue
        if row is None:
            time.sleep(0.4)
            continue
        download_id = str(row["id"])
        _CANCEL.clear()
        _SAMPLES.clear()
        _PROGRESS[download_id] = {"completed": 0, "total": 0, "rate": 0}

        seen_digests: set[str] = set()

        def on_event(event: dict[str, object]) -> None:
            completed = event.get("completed")
            total = event.get("total")
            digest = event.get("digest")
            if isinstance(digest, str) and digest.startswith("sha256:") and digest not in seen_digests:
                seen_digests.add(digest)
                _save_digests(download_id, seen_digests)
            _note_progress(
                download_id,
                completed if isinstance(completed, int) else None,
                total if isinstance(total, int) else None,
            )

        try:
            outcome = pull_events(str(row["model"]), _CANCEL, on_event)
        except Exception:
            outcome = "error"
        if _CANCEL.is_set():
            _PROGRESS.pop(download_id, None)
            continue
        try:
            if outcome == "success":
                _finish(download_id, "done")
            else:
                _finish(download_id, "error", "models.pull.failed")
        except Exception:
            log.warning("could not record download %s outcome", download_id, exc_info=True)


def ensure_worker() -> None:
    global _THREAD
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return
        try:
            recover_after_restart()
        except Exception:
            return
        _THREAD = threading.Thread(target=_loop, name="model-downloads", daemon=True)
        _THREAD.start()
