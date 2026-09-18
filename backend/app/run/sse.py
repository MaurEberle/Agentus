from __future__ import annotations

import queue
from typing import Any

from app.common.secrets import mask_obj
from app.run.limits import SSE_QUEUE_MAX

_subscribers: list[queue.Queue] = []


def publish(event: str, data: dict[str, Any]) -> None:
    payload = mask_obj(data)
    dead: list[queue.Queue] = []
    for q in list(_subscribers):
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
    _subscribers.append(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)
