"""Help reindex runs off the HTTP request so leaving a screen cannot cancel it."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Literal

log = logging.getLogger("agentus.help")

ReindexState = Literal["idle", "running", "ready", "error"]


@dataclass(frozen=True)
class ReindexSnapshot:
    state: ReindexState
    message_key: str | None = None
    job_id: str | None = None


@dataclass
class _Job:
    job_id: str
    state: ReindexState
    message_key: str | None = None


_lock = threading.Lock()
_job: _Job | None = None
_thread: threading.Thread | None = None


def snapshot() -> ReindexSnapshot:
    with _lock:
        if _job is None:
            return ReindexSnapshot(state="idle")
        return ReindexSnapshot(
            state=_job.state,
            message_key=_job.message_key,
            job_id=_job.job_id,
        )


def begin() -> ReindexSnapshot:
    global _job, _thread
    with _lock:
        if _job is not None and _job.state == "running" and _thread is not None and _thread.is_alive():
            return ReindexSnapshot(state="running", job_id=_job.job_id)
        job = _Job(job_id=str(uuid.uuid4()), state="running")
        _job = job
        thread = threading.Thread(
            target=_worker,
            args=(job.job_id,),
            name="help-reindex",
            daemon=True,
        )
        _thread = thread
        thread.start()
        return ReindexSnapshot(state="running", job_id=job.job_id)


def reset_for_tests() -> None:
    global _job, _thread
    with _lock:
        thread = _thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=5)
    with _lock:
        _job = None
        _thread = None


def _worker(job_id: str) -> None:
    from app.help.index import reindex

    try:
        state, key = reindex()
    except Exception as exc:
        log.warning("help reindex failed: %s", type(exc).__name__)
        state, key = "error", "help.index.failed"
    if state == "error" and not key:
        key = "help.index.failed"
    with _lock:
        if _job is None or _job.job_id != job_id:
            return
        _job.state = state
        _job.message_key = key
