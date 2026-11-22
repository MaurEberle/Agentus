from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Response
from pydantic import Field

from app.db.runs import (
    call_stats_by_model,
    delete_runs,
    count_logs,
    get_run,
    list_calls,
    list_logs,
    list_runs,
    list_steps,
    purge_older_than,
)
from app.http.app import ApiModel
from app.http.errors import AppError

router = APIRouter(tags=["runs"])


class DeleteRunsBody(ApiModel):
    ids: list[str]


class PurgeBody(ApiModel):
    # M15: at least one day; 0 used to become 90 and a negative value deleted everything.
    older_than_days: int | None = Field(default=None, alias="olderThanDays", ge=1, le=36_500)

    model_config = ApiModel.model_config


@router.get("/runs")
def get_runs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    since: str | None = None,
    networkId: str | None = None,
    outcome: str | None = None,
    model: str | None = None,
    q: str | None = None,
    error: str | None = None,
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
) -> dict[str, Any]:
    items, total = list_runs(
        limit=limit,
        offset=offset,
        since=since,
        from_ts=from_ts,
        to_ts=to_ts,
        network_id=networkId,
        outcome=outcome.split(",") if outcome else None,
        model=model,
        q=q,
        error=error,
    )
    camel = [_camel_run(item) for item in items]
    return {"items": camel, "total": total}


@router.get("/runs/calls")
def get_calls(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    since: str | None = None,
    networkId: str | None = None,
    outcome: str | None = None,
    model: str | None = None,
    q: str | None = None,
    error: str | None = None,
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
) -> dict[str, Any]:
    # H10: the same filters as GET /runs, including the time range, and newest first.
    filters: dict[str, Any] = {
        "since": since,
        "from_ts": from_ts,
        "to_ts": to_ts,
        "network_id": networkId,
        "outcome": outcome.split(",") if outcome else None,
        "model": model,
        "q": q,
        "error": error,
    }
    rows = list_calls(None, limit=limit, offset=offset, newest_first=True, **filters)
    return {
        "items": [_camel_call(row) for row in rows],
        # Counted over every call of the filtered runs, not over the page above.
        "byModel": [_camel_model_stats(row) for row in call_stats_by_model(**filters)],
    }


@router.get("/runs/{run_id}")
def get_one(run_id: str) -> dict[str, Any]:
    row = get_run(run_id)
    if row is None:
        raise AppError("db.notFound", status_code=404)
    body = _camel_run(row)
    body["calls"] = [_camel_call(item) for item in list_calls(run_id)]
    body["steps"] = [_camel_step(item) for item in list_steps(run_id)]
    return body


LOGS_DEFAULT_LIMIT = 5_000


@router.get("/runs/{run_id}/logs")
def get_logs(
    run_id: str,
    level: str | None = None,
    q: str | None = None,
    nodeId: str | None = None,
    limit: int = Query(default=LOGS_DEFAULT_LIMIT, ge=1, le=50_000),
) -> dict[str, Any]:
    """The newest ``limit`` log lines, oldest first; ``total`` counts all matches (M16)."""
    if get_run(run_id) is None:
        raise AppError("db.notFound", status_code=404)
    rows = list_logs(run_id, level=level, q=q, node_id=nodeId, limit=limit)
    total = count_logs(run_id, level=level, q=q, node_id=nodeId)
    return {"items": [_camel_log(row) for row in rows], "total": total}


@router.delete("/runs", status_code=204)
def delete_many(body: DeleteRunsBody) -> Response:
    for run_id in body.ids:
        row = get_run(run_id)
        if row and row.get("outcome") == "running":
            raise AppError("run.busy", status_code=409)
    delete_runs(body.ids)
    return Response(status_code=204)


@router.post("/runs/purge")
def purge(body: PurgeBody) -> dict[str, int]:
    """Delete finished runs older than the given days, or than the retention setting.

    Retention "unlimited" (None) deletes nothing.
    """
    days = body.older_than_days
    if days is None:
        from app.settings.service import load_settings

        days = load_settings().history_retention_days
    if days is None:
        return {"deleted": 0}
    return {"deleted": purge_older_than(int(days))}


def _camel_run(row: dict[str, Any]) -> dict[str, Any]:
    run_id = row["id"]
    return {
        "id": run_id,
        "runId": run_id,
        "networkId": row["network_id"],
        "networkName": row["network_name"],
        "startedAt": row["started_at"],
        "endedAt": row.get("ended_at"),
        "outcome": row["outcome"],
        "errorMessage": row.get("error_message"),
        "errorClass": row.get("error_class"),
        "errorNodeId": row.get("error_node_id"),
        "errorNodeName": row.get("error_node_name"),
        "graphSnapshot": row.get("graph_snapshot"),
        "chat": row.get("chat"),
        "memory": row.get("memory"),
        "models": _camel_models(row.get("models") or []),
        "calls": [],
        "steps": [],
    }


def _camel_models(models: object) -> list[dict[str, str]]:
    if not isinstance(models, list):
        return []
    items: list[dict[str, str]] = []
    for item in models:
        if isinstance(item, str) and item.strip():
            items.append({"provider": "ollama", "model": item})
        elif isinstance(item, dict):
            name = str(item.get("model") or item.get("name") or "").strip()
            provider = str(item.get("provider") or "ollama").strip() or "ollama"
            if name:
                items.append({"provider": provider, "model": name})
    return items


def _camel_log(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "runId": row["run_id"],
        "ts": row["ts"],
        "level": row["level"],
        "nodeId": row.get("node_id"),
        "nodeName": row.get("node_name"),
        "message": row["message"],
        "payload": row.get("payload"),
        "stack": row.get("stack"),
    }


def _camel_call(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "runId": row["run_id"],
        "nodeId": row.get("node_id"),
        "nodeName": row.get("node_name"),
        "provider": row["provider"],
        "model": row["model"],
        "ok": row["ok"],
        "durationMs": row.get("duration_ms"),
        "tokensIn": row.get("tokens_in"),
        "tokensOut": row.get("tokens_out"),
        "errorMessage": row.get("error_message"),
    }


def _camel_model_stats(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": row["provider"],
        "model": row["model"],
        "calls": row["calls"],
        "ok": row["ok"],
        "error": row["error"],
        "medianMs": row.get("median_ms"),
        "tokensIn": row.get("tokens_in"),
        "tokensOut": row.get("tokens_out"),
    }


def _camel_step(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodeId": row["node_id"],
        "nodeName": row.get("node_name"),
        "role": row.get("role"),
        "type": row.get("type"),
        "status": row["status"],
        "waitReason": row.get("wait_reason"),
        "errorMessage": row.get("error_message"),
    }
