"""History store. Dict keys are snake_case; routers map camelCase."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.engine import json_dumps, json_loads, locked, transaction, utc_now
from app.db.errors import StoreUnavailable

_JSON_FIELDS = frozenset({"graph_snapshot", "chat", "models", "memory"})
_UPDATE_FIELDS = frozenset(
    {
        "ended_at",
        "outcome",
        "error_message",
        "error_class",
        "error_node_id",
        "error_node_name",
        "graph_snapshot",
        "chat",
        "models",
        "updated_at",
        "memory",
    }
)


def _dump_optional(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json_dumps(value)


def _run_dict(row: Any) -> dict[str, Any]:
    models = json_loads(row["models"], default=[])
    if not isinstance(models, list):
        models = []
    graph = json_loads(row["graph_snapshot"], default=None) if row["graph_snapshot"] else None
    chat = json_loads(row["chat"], default=None) if row["chat"] else None
    return {
        "id": row["id"],
        "network_id": row["network_id"],
        "network_name": row["network_name"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "outcome": row["outcome"],
        "error_message": row["error_message"],
        "error_class": row["error_class"],
        "error_node_id": row["error_node_id"],
        "error_node_name": row["error_node_name"],
        "graph_snapshot": graph,
        "chat": chat,
        "models": models,
        "memory": _optional_json(row, "memory"),
    }


def _optional_json(row: Any, key: str) -> Any:
    try:
        raw = row[key]
    except (IndexError, KeyError):
        return None
    if not raw:
        return None
    return json_loads(raw, default=None)


def _log_dict(row: Any) -> dict[str, Any]:
    payload = json_loads(row["payload"], default=None) if row["payload"] is not None else None
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "ts": row["ts"],
        "level": row["level"],
        "node_id": row["node_id"],
        "node_name": row["node_name"],
        "message": row["message"],
        "payload": payload,
        "stack": row["stack"],
    }


def _call_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "node_id": row["node_id"],
        "node_name": row["node_name"],
        "provider": row["provider"],
        "model": row["model"],
        "ok": bool(row["ok"]),
        "duration_ms": row["duration_ms"],
        "tokens_in": row["tokens_in"],
        "tokens_out": row["tokens_out"],
        "error_message": row["error_message"],
    }


def _step_dict(row: Any) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "node_id": row["node_id"],
        "node_name": row["node_name"],
        "role": row["role"],
        "type": row["type"],
        "status": row["status"],
        "wait_reason": row["wait_reason"],
        "error_message": row["error_message"],
    }


def _run_filters(
    *,
    since: str | None,
    from_ts: str | None,
    to_ts: str | None,
    network_id: str | None,
    outcome: list[str] | None,
    model: str | None,
    q: str | None,
    alias: str = "runs",
) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []
    if since:
        clauses.append(f"{alias}.started_at >= ?")
        params.append(since)
    if from_ts:
        clauses.append(f"{alias}.started_at >= ?")
        params.append(from_ts)
    if to_ts:
        clauses.append(f"{alias}.started_at <= ?")
        params.append(to_ts)
    if network_id:
        clauses.append(f"{alias}.network_id = ?")
        params.append(network_id)
    if outcome:
        placeholders = ",".join("?" * len(outcome))
        clauses.append(f"{alias}.outcome IN ({placeholders})")
        params.extend(outcome)
    if model:
        clauses.append(
            f"""
            (
              EXISTS (
                SELECT 1 FROM json_each({alias}.models) AS j
                WHERE j.value = ? OR json_extract(j.value, '$.model') = ?
              )
              OR EXISTS (
                SELECT 1 FROM llm_calls c
                WHERE c.run_id = {alias}.id AND c.model = ?
              )
            )
            """
        )
        params.extend([model, model, model])
    if q:
        like = f"%{q}%"
        clauses.append(
            f"""
            (
              {alias}.id LIKE ? OR {alias}.network_name LIKE ?
              OR IFNULL({alias}.error_message, '') LIKE ?
            )
            """
        )
        params.extend([like, like, like])
    sql = (" AND " + " AND ".join(clauses)) if clauses else ""
    return sql, params


def insert_run(
    *,
    id: str,
    network_id: str,
    network_name: str,
    started_at: str,
    outcome: str = "running",
    graph_snapshot: object | None = None,
    models: list[str] | None = None,
) -> None:
    with transaction("history") as conn:
        conn.execute(
            """
            INSERT INTO runs (
              id, network_id, network_name, started_at, outcome, graph_snapshot, models, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id,
                network_id,
                network_name,
                started_at,
                outcome,
                _dump_optional(graph_snapshot),
                json_dumps(models or []),
                started_at,
            ),
        )


def _activity_ended_at(conn: Any, run_id: str, started_at: str) -> str:
    log_row = conn.execute(
        """
        SELECT MAX(ts) AS ts FROM run_logs
        WHERE run_id = ? AND message != 'run.interrupted'
        """,
        (run_id,),
    ).fetchone()
    run_row = conn.execute(
        "SELECT updated_at FROM runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    candidates = [started_at]
    if log_row is not None and log_row["ts"]:
        candidates.append(str(log_row["ts"]))
    if run_row is not None and run_row["updated_at"]:
        candidates.append(str(run_row["updated_at"]))
    return max(candidates)


def touch_run(id: str, *, at: str | None = None) -> None:
    ts = at or utc_now()
    try:
        with transaction("history") as conn:
            conn.execute(
                "UPDATE runs SET updated_at = ? WHERE id = ? AND outcome = 'running'",
                (ts, id),
            )
    except StoreUnavailable:
        return


def abandon_orphaned_runs(*, ended_at: str | None = None) -> int:
    """Mark leftover ``running`` rows cancelled. Safe at process start."""
    detected = utc_now()
    try:
        with transaction("history") as conn:
            rows = conn.execute(
                "SELECT id, started_at FROM runs WHERE outcome = 'running'"
            ).fetchall()
            if not rows:
                return 0
            ids = [str(row["id"]) for row in rows]
            for row in rows:
                run_id = str(row["id"])
                ended = ended_at or _activity_ended_at(conn, run_id, str(row["started_at"]))
                conn.execute(
                    """
                    UPDATE runs
                    SET outcome = 'cancelled', ended_at = ?
                    WHERE id = ? AND outcome = 'running'
                    """,
                    (ended, run_id),
                )
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"""
                UPDATE run_steps
                SET status = 'error',
                    error_message = COALESCE(error_message, 'run.interrupted')
                WHERE run_id IN ({placeholders})
                  AND status IN ('waiting', 'running')
                """,
                ids,
            )
            for run_id in ids:
                conn.execute(
                    """
                    INSERT INTO run_logs (
                      id, run_id, ts, level, node_id, node_name, message, payload, stack
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        run_id,
                        detected,
                        "warn",
                        None,
                        None,
                        "run.interrupted",
                        None,
                        None,
                    ),
                )
            return len(ids)
    except StoreUnavailable:
        return 0


def repair_interrupted_ended_at() -> int:
    """Fix durations that used process-restart time instead of last activity."""
    try:
        with transaction("history") as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT runs.id, runs.started_at, runs.ended_at
                FROM runs
                JOIN run_logs ON run_logs.run_id = runs.id
                WHERE runs.outcome = 'cancelled'
                  AND run_logs.message = 'run.interrupted'
                """
            ).fetchall()
            changed = 0
            for row in rows:
                ended = _activity_ended_at(conn, str(row["id"]), str(row["started_at"]))
                if ended != row["ended_at"]:
                    conn.execute(
                        "UPDATE runs SET ended_at = ? WHERE id = ?",
                        (ended, row["id"]),
                    )
                    changed += 1
            return changed
    except StoreUnavailable:
        return 0


def _run_assignments(fields: dict[str, Any]) -> tuple[str, list[object]]:
    assignments: list[str] = []
    params: list[object] = []
    for key, value in fields.items():
        assignments.append(f"{key} = ?")
        if key in _JSON_FIELDS:
            params.append(_dump_optional(value) if key != "models" else json_dumps(value or []))
        else:
            params.append(value)
    return ", ".join(assignments), params


def update_run(id: str, **fields: Any) -> None:
    updates = {key: value for key, value in fields.items() if key in _UPDATE_FIELDS}
    if not updates:
        return
    assignments, params = _run_assignments(updates)
    params.append(id)
    with transaction("history") as conn:
        conn.execute(
            f"UPDATE runs SET {assignments} WHERE id = ?",
            params,
        )


def complete_run(id: str, **fields: Any) -> bool:
    """Write a terminal outcome only while the row is still ``running``."""
    updates = {key: value for key, value in fields.items() if key in _UPDATE_FIELDS}
    if "outcome" not in updates:
        return False
    assignments, params = _run_assignments(updates)
    params.append(id)
    with transaction("history") as conn:
        cur = conn.execute(
            f"UPDATE runs SET {assignments} WHERE id = ? AND outcome = 'running'",
            params,
        )
        return int(cur.rowcount) > 0


def get_run(id: str) -> dict[str, Any] | None:
    with locked("history") as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (id,)).fetchone()
    return None if row is None else _run_dict(row)


def list_runs(
    *,
    limit: int = 50,
    offset: int = 0,
    since: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    network_id: str | None = None,
    outcome: list[str] | None = None,
    model: str | None = None,
    q: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    where, params = _run_filters(
        since=since,
        from_ts=from_ts,
        to_ts=to_ts,
        network_id=network_id,
        outcome=outcome,
        model=model,
        q=q,
    )
    with locked("history") as conn:
        total_row = conn.execute(
            f"SELECT COUNT(*) AS n FROM runs WHERE 1=1{where}", params
        ).fetchone()
        total = int(total_row["n"]) if total_row else 0
        rows = conn.execute(
            f"""
            SELECT * FROM runs WHERE 1=1{where}
            ORDER BY started_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    return [_run_dict(row) for row in rows], total


def delete_runs(ids: list[str]) -> None:
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    with transaction("history") as conn:
        conn.execute(f"DELETE FROM runs WHERE id IN ({placeholders})", ids)


def purge_older_than(days: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with transaction("history") as conn:
        cur = conn.execute(
            """
            DELETE FROM runs
            WHERE outcome != 'running' AND started_at < ?
            """,
            (cutoff,),
        )
        return int(cur.rowcount)


def insert_log(
    *,
    run_id: str,
    message: str,
    id: str | None = None,
    ts: str | None = None,
    level: str = "info",
    node_id: str | None = None,
    node_name: str | None = None,
    payload: object | None = None,
    stack: str | None = None,
) -> None:
    with transaction("history") as conn:
        conn.execute(
            """
            INSERT INTO run_logs (
              id, run_id, ts, level, node_id, node_name, message, payload, stack
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id or str(uuid.uuid4()),
                run_id,
                ts or utc_now(),
                level,
                node_id,
                node_name,
                message,
                _dump_optional(payload),
                stack,
            ),
        )


def list_logs(
    run_id: str,
    *,
    level: str | None = None,
    q: str | None = None,
    node_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = ["run_id = ?"]
    params: list[object] = [run_id]
    if level:
        clauses.append("level = ?")
        params.append(level)
    if node_id:
        clauses.append("node_id = ?")
        params.append(node_id)
    if q:
        clauses.append("message LIKE ?")
        params.append(f"%{q}%")
    where = " AND ".join(clauses)
    with locked("history") as conn:
        rows = conn.execute(
            f"SELECT * FROM run_logs WHERE {where} ORDER BY ts ASC, id ASC",
            params,
        ).fetchall()
    return [_log_dict(row) for row in rows]


def insert_call(
    *,
    run_id: str,
    provider: str,
    model: str,
    ok: bool,
    id: str | None = None,
    node_id: str | None = None,
    node_name: str | None = None,
    duration_ms: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    error_message: str | None = None,
) -> None:
    with transaction("history") as conn:
        conn.execute(
            """
            INSERT INTO llm_calls (
              id, run_id, node_id, node_name, provider, model, ok,
              duration_ms, tokens_in, tokens_out, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id or str(uuid.uuid4()),
                run_id,
                node_id,
                node_name,
                provider,
                model,
                1 if ok else 0,
                duration_ms,
                tokens_in,
                tokens_out,
                error_message,
            ),
        )


def list_calls(
    run_id: str | None = None,
    *,
    limit: int = 50,
    offset: int = 0,
    since: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    network_id: str | None = None,
    outcome: list[str] | None = None,
    model: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[object] = []
    if run_id:
        clauses.append("llm_calls.run_id = ?")
        params.append(run_id)
    extra, extra_params = _run_filters(
        since=since,
        from_ts=from_ts,
        to_ts=to_ts,
        network_id=network_id,
        outcome=outcome,
        model=model,
        q=q,
        alias="runs",
    )
    params.extend(extra_params)
    where = ""
    if clauses or extra:
        parts = clauses[:]
        if extra:
            parts.append(extra.removeprefix(" AND "))
        where = " WHERE " + " AND ".join(p for p in parts if p)
    with locked("history") as conn:
        rows = conn.execute(
            f"""
            SELECT llm_calls.* FROM llm_calls
            JOIN runs ON runs.id = llm_calls.run_id
            {where}
            ORDER BY llm_calls.id
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    return [_call_dict(row) for row in rows]


def upsert_step(
    *,
    run_id: str,
    node_id: str,
    node_name: str | None = None,
    role: str | None = None,
    type: str | None = None,
    status: str | None = None,
    wait_reason: str | None = None,
    error_message: str | None = None,
) -> None:
    with transaction("history") as conn:
        conn.execute(
            """
            INSERT INTO run_steps (
              run_id, node_id, node_name, role, type, status, wait_reason, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, node_id) DO UPDATE SET
              node_name = excluded.node_name,
              role = excluded.role,
              type = excluded.type,
              status = excluded.status,
              wait_reason = excluded.wait_reason,
              error_message = excluded.error_message
            """,
            (run_id, node_id, node_name, role, type, status, wait_reason, error_message),
        )


def list_steps(run_id: str) -> list[dict[str, Any]]:
    with locked("history") as conn:
        rows = conn.execute(
            "SELECT * FROM run_steps WHERE run_id = ? ORDER BY node_id",
            (run_id,),
        ).fetchall()
    return [_step_dict(row) for row in rows]
