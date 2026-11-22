"""GET /api/health and GET /api/about. No dataDir, no secrets."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter()


def _store_states() -> dict[str, str] | None:
    try:
        from app.db.bootstrap import get_data_location
    except ImportError:
        return None
    try:
        location = get_data_location()
    except Exception:
        return None
    items = location.get("stores") or []
    states: dict[str, str] = {}
    for item in items:
        store_id = item.get("id")
        state = item.get("state")
        if isinstance(store_id, str) and isinstance(state, str):
            states[store_id] = state
    return states or None


def _runtime_block() -> dict[str, bool] | None:
    try:
        from app.runtime import ping_ollama
    except ImportError:
        return None
    try:
        result = ping_ollama()
        return {"ok": bool(getattr(result, "ok", False))}
    except Exception:
        return {"ok": False}


@router.get("/health")
def health() -> dict[str, Any]:
    body: dict[str, Any] = {"ok": True}
    stores = _store_states()
    if stores is not None:
        body["stores"] = stores
    return body


@router.post("/app/restart")
def app_restart() -> dict[str, Any]:
    """Close and reopen the desktop app. Refused while a run is active."""
    from app.host.restart import request_restart
    from app.http.errors import AppError
    from app.settings.service import is_run_busy

    if is_run_busy():
        raise AppError("app.restart.busy", status_code=409)
    return {"restart": request_restart()}


@router.post("/app/open-logs")
def app_open_logs() -> dict[str, Any]:
    """Open the folder with agentus.log in the file manager. The path itself is not sent."""
    from app.applog import open_log_dir

    return {"opened": open_log_dir()}


@router.get("/about")
def about() -> dict[str, Any]:
    from app.http.app import api_version

    body: dict[str, Any] = {"apiVersion": api_version()}
    runtime = _runtime_block()
    if runtime is not None:
        body["runtime"] = runtime
    return body
