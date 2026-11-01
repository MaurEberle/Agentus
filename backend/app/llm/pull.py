"""Stream an Ollama pull of one ``hf.co`` tag. Cancel closes the upstream request."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator

from app.common.http import client
from app.llm.hub import valid_pull_model
from app.runtime.urls import ollama_native_root, settings_roots


def _root() -> str:
    return settings_roots()[0] or ollama_native_root("")


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
    try:
        with client(unbounded_read=True) as http:
            with http.stream("POST", url, json={"model": name, "stream": True}) as response:
                if response.status_code >= 400:
                    return "error"
                saw_success = False
                for line in response.iter_lines():
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
                    if isinstance(completed, int):
                        event["completed"] = completed
                    if isinstance(total, int):
                        event["total"] = total
                    if on_event is not None:
                        on_event(event)
                    if status == "success":
                        saw_success = True
                if cancel is not None and cancel.is_set():
                    return "cancelled"
                return "success" if saw_success else "success"
    except Exception:
        if cancel is not None and cancel.is_set():
            return "cancelled"
        return "error"


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
                    yield json.dumps({"status": "success"}) + "\n"
    except Exception:
        yield json.dumps({"status": "error", "messageKey": "models.pull.failed"}) + "\n"
