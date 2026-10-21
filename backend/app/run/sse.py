from __future__ import annotations

import queue
import threading
from typing import Any

from app.common.secrets import mask_obj
from app.run.limits import SSE_QUEUE_MAX

_subscribers: list[queue.Queue] = []
_lock = threading.Lock()


def publish(event: str, data: dict[str, Any]) -> None:
    payload = mask_obj(data)
    dead: list[queue.Queue] = []
    with _lock:
        subscribers = list(_subscribers)
    for q in subscribers:
        try:
            if q.maxsize and q.qsize() >= SSE_QUEUE_MAX:
                try:
                    q.get_nowait()
                except queue.Empty:
                    pass
            q.put_nowait((event, payload))
        except Exception:
            dead.append(q)
    for q in dead:
        unsubscribe(q)


def subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=SSE_QUEUE_MAX)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    with _lock:
        if q in _subscribers:
            _subscribers.remove(q)
