from __future__ import annotations

import threading

_current: threading.Event | None = None
_lock = threading.Lock()


def begin_request() -> threading.Event:
    global _current
    event = threading.Event()
    with _lock:
        _current = event
    return event


def abort_current() -> None:
    with _lock:
        if _current is not None:
            _current.set()


def end_request(event: threading.Event) -> None:
    global _current
    with _lock:
        if _current is event:
            _current = None
