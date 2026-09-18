from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Response

from app.db.runs import (
    delete_runs,
    get_run,
    list_calls,
    list_logs,
    list_runs,
    purge_older_than,
)
from app.http.app import ApiModel
from app.http.errors import AppError

router = APIRouter(tags=["runs"])


class DeleteRunsBody(ApiModel):
    ids: list[str]


class PurgeBody(ApiModel):
    older_than_days: int | None = None

    model_config = ApiModel.model_config


@router.get("/runs")
def get_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    since: str | None = None,
    networkId: str | None = None,
    outcome: str | None = None,
    model: str | None = None,
    q: str | None = None,
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
    )
    camel = [_camel_run(item) for item in items]
    return {"items": camel, "total": total}


@router.get("/runs/calls")
def get_calls(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    networkId: str | None = None,
    outcome: str | None = None,
    model: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    rows = list_calls(
        None,
        limit=limit,
        offset=offset,
        network_id=networkId,
        outcome=outcome.split(",") if outcome else None,
        model=model,
        q=q,
    )
    return {"items": [_camel_call(row) for row in rows]}


@router.get("/runs/{run_id}")
def get_one(run_id: str) -> dict[str, Any]:
    row = get_run(run_id)
    if row is None:
        raise AppError("db.notFound", status_code=404)
    return _camel_run(row)


@router.get("/runs/{run_id}/logs")
def get_logs(
    run_id: str,
    level: str | None = None,
    q: str | None = None,
    nodeId: str | None = None,
) -> dict[str, Any]:
    if get_run(run_id) is None:
        raise AppError("db.notFound", status_code=404)
    rows = list_logs(run_id, level=level, q=q, node_id=nodeId)
    return {"items": [_camel_log(row) for row in rows]}


@router.delete("/runs", status_code=204)
def delete_many(body: DeleteRunsBody) -> Response:
    for run_id in body.ids:
        row = get_run(run_id)
        if row and row.get("outcome") == "running":
            raise AppError("run.busy", status_code=409)
    delete_runs(body.ids)
    return Response(status_code=204)


@router.post("/runs/purge")
def purge(body: dict[str, Any]) -> dict[str, int]:
    days = int(body.get("olderThanDays") or body.get("older_than_days") or 90)
    return {"deleted": purge_older_than(days)}


def _camel_run(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "networkId": row["network_id"],
        "networkName": row["network_name"],
        "startedAt": row["started_at"],
        "endedAt": row.get("ended_at"),
        "outcome": row["outcome"],
        "errorMessage": row.get("error_message"),
        "graphSnapshot": row.get("graph_snapshot"),
        "chat": row.get("chat"),
        "models": row.get("models") or [],
    }


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
        "provider": row["provider"],
        "model": row["model"],
        "ok": row["ok"],
        "durationMs": row.get("duration_ms"),
        "tokensIn": row.get("tokens_in"),
        "tokensOut": row.get("tokens_out"),
    }
