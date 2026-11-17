"""Stream an Ollama pull of one ``hf.co`` tag. Cancel closes the upstream request."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator

from app.common.http import client
from app.llm.hub import valid_pull_model
from app.runtime.urls import ollama_native_root, settings_roots


def _root() -> str:
    return settings_roots()[0] or ollama_native_root("")


# M19: a pull that sends nothing for this long is dead. Verifying a very large blob
# is silent for minutes, so the limit is generous.
STALL_SEC = 900.0
_WATCH_TICK = 0.5


def _watch(response, cancel: threading.Event | None, last: list[float], done: threading.Event, state: dict) -> None:
    """Close the stream on cancel or stall; the reading thread then leaves iter_lines."""
    while not done.wait(_WATCH_TICK):
        cancelled = cancel is not None and cancel.is_set()
        stalled = time.monotonic() - last[0] > STALL_SEC
        if cancelled or stalled:
            state["stalled"] = stalled and not cancelled
            try:
                response.close()
            except Exception:
                pass
            return


def pull_events(
    model: str,
    cancel: threading.Event | None = None,
    on_event: Callable[[dict[str, object]], None] | None = None,
) -> str:
    """Run one pull. Returns ``success``, ``cancelled``, or ``error``."""
    name = (model or "").strip()
    if not valid_pull_model(name):
        return "error"
    url = f"{_root()}/api/pull"
    done = threading.Event()
    state: dict[str, bool] = {}
    try:
        with client(unbounded_read=True) as http:
            with http.stream("POST", url, json={"model": name, "stream": True}) as response:
                if response.status_code >= 400:
                    return "error"
                last = [time.monotonic()]
                threading.Thread(
                    target=_watch,
                    args=(response, cancel, last, done, state),
                    name="pull-watch",
                    daemon=True,
                ).start()
                saw_success = False
                for line in response.iter_lines():
                    last[0] = time.monotonic()
                    if cancel is not None and cancel.is_set():
                        return "cancelled"
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("error"):
                        return "error"
                    status = str(payload.get("status") or "")
                    event: dict[str, object] = {"status": status or "pulling"}
                    completed = payload.get("completed")
                    total = payload.get("total")
                    digest = payload.get("digest")
                    if isinstance(completed, int):
                        event["completed"] = completed
                    if isinstance(total, int):
                        event["total"] = total
                    if isinstance(digest, str):
                        event["digest"] = digest
                    if on_event is not None:
                        on_event(event)
                    if status == "success":
                        saw_success = True
                if cancel is not None and cancel.is_set():
                    return "cancelled"
                # M19: a stream that ends without "success" did not finish the pull.
                return "success" if saw_success and not state.get("stalled") else "error"
    except Exception:
        if cancel is not None and cancel.is_set():
            return "cancelled"
        return "error"
    finally:
        done.set()


def pull_lines(model: str) -> Iterator[str]:
    name = (model or "").strip()
    if not valid_pull_model(name):
        yield json.dumps({"status": "error", "messageKey": "models.pull.invalid"}) + "\n"
        return
    url = f"{_root()}/api/pull"
    try:
        with client(unbounded_read=True) as http:
            with http.stream("POST", url, json={"model": name, "stream": True}) as response:
                if response.status_code >= 400:
                    yield json.dumps({"status": "error", "messageKey": "models.pull.failed"}) + "\n"
                    return
                saw_success = False
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    status = str(payload.get("status") or "")
                    if payload.get("error"):
                        yield json.dumps({"status": "error", "messageKey": "models.pull.failed"}) + "\n"
                        return
                    event: dict[str, object] = {"status": status or "pulling"}
                    completed = payload.get("completed")
                    total = payload.get("total")
                    if isinstance(completed, int):
                        event["completed"] = completed
                    if isinstance(total, int):
                        event["total"] = total
                    if status == "success":
                        saw_success = True
                    yield json.dumps(event) + "\n"
                if not saw_success:
                    # M19: no "success" line means the pull did not finish.
                    yield json.dumps({"status": "error", "messageKey": "models.pull.failed"}) + "\n"
    except Exception:
        yield json.dumps({"status": "error", "messageKey": "models.pull.failed"}) + "\n"
