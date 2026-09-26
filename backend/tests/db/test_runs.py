from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db import init
from app.db.engine import close_store, utc_now
from app.db.errors import StoreUnavailable
from app.db.networks import NetworkRow, list_networks, upsert_network
from app.db.runs import (
    abandon_orphaned_runs,
    complete_run,
    delete_runs,
    get_run,
    insert_call,
    insert_log,
    insert_run,
    list_calls,
    list_logs,
    list_runs,
    list_steps,
    purge_older_than,
    repair_interrupted_ended_at,
    touch_run,
    update_run,
    upsert_step,
)


def test_list_runs_query_by_name() -> None:
    init()
    now = utc_now()
    insert_run(id="run-a", network_id="n1", network_name="Demo-Netz", started_at=now)
    insert_run(id="run-b", network_id="n2", network_name="Support", started_at=now)
    items, total = list_runs(q="Demo")
    assert total == 1
    assert items[0]["id"] == "run-a"


def test_abandon_orphaned_runs() -> None:
    init()
    now = utc_now()
    insert_run(
        id="run-live",
        network_id="n1",
        network_name="Demo",
        started_at=now,
        outcome="running",
    )
    insert_run(
        id="run-ok",
        network_id="n1",
        network_name="Demo",
        started_at=now,
        outcome="succeeded",
    )
    upsert_step(run_id="run-live", node_id="ag", status="running")
    upsert_step(run_id="run-live", node_id="end", status="idle")
    assert abandon_orphaned_runs() == 1
    live = get_run("run-live")
    assert live is not None
    assert live["outcome"] == "cancelled"
    assert live["ended_at"] == now
    ok = get_run("run-ok")
    assert ok is not None
    assert ok["outcome"] == "succeeded"
    logs = list_logs("run-live")
    assert any(row["message"] == "run.interrupted" for row in logs)
    steps = {row["node_id"]: row for row in list_steps("run-live")}
    assert steps["ag"]["status"] == "error"
    assert steps["end"]["status"] == "idle"
    assert abandon_orphaned_runs() == 0


def test_abandon_uses_last_activity_not_now() -> None:
    init()
    started = "2026-09-20T18:43:15.000000+00:00"
    last = "2026-09-20T18:48:20.000000+00:00"
    insert_run(
        id="run-ghost",
        network_id="n1",
        network_name="Demo",
        started_at=started,
        outcome="running",
    )
    insert_log(run_id="run-ghost", message="run.llm.start", ts=last, level="info")
    assert abandon_orphaned_runs() == 1
    row = get_run("run-ghost")
    assert row is not None
    assert row["outcome"] == "cancelled"
    assert row["ended_at"] == last
    logs = list_logs("run-ghost")
    interrupted = [item for item in logs if item["message"] == "run.interrupted"]
    assert interrupted
    assert interrupted[0]["ts"] != last


def test_repair_interrupted_ended_at() -> None:
    init()
    started = "2026-09-20T18:43:15.000000+00:00"
    last = "2026-09-20T18:48:20.000000+00:00"
    restart = "2026-09-20T20:30:43.000000+00:00"
    insert_run(
        id="run-old",
        network_id="n1",
        network_name="Demo",
        started_at=started,
        outcome="cancelled",
    )
    update_run("run-old", ended_at=restart)
    insert_log(run_id="run-old", message="run.llm.start", ts=last, level="info")
    insert_log(run_id="run-old", message="run.interrupted", ts=restart, level="warn")
    assert repair_interrupted_ended_at() == 1
    row = get_run("run-old")
    assert row is not None
    assert row["ended_at"] == last
    assert repair_interrupted_ended_at() == 0


def test_touch_run_updates_activity() -> None:
    init()
    started = "2026-09-20T19:00:00.000000+00:00"
    later = "2026-09-20T19:10:00.000000+00:00"
    insert_run(
        id="run-live",
        network_id="n1",
        network_name="Demo",
        started_at=started,
        outcome="running",
    )
    touch_run("run-live", at=later)
    assert abandon_orphaned_runs() == 1
    row = get_run("run-live")
    assert row is not None
    assert row["ended_at"] == later


def test_complete_run_only_while_running() -> None:
    init()
    insert_run(
        id="run-done",
        network_id="n1",
        network_name="Demo",
        started_at=utc_now(),
        outcome="succeeded",
    )
    assert complete_run("run-done", outcome="cancelled", ended_at=utc_now()) is False
    row = get_run("run-done")
    assert row is not None
    assert row["outcome"] == "succeeded"
    insert_run(
        id="run-live",
        network_id="n1",
        network_name="Demo",
        started_at=utc_now(),
        outcome="running",
    )
    assert complete_run("run-live", outcome="cancelled", ended_at=utc_now()) is True
    live = get_run("run-live")
    assert live is not None
    assert live["outcome"] == "cancelled"


def test_init_reclaims_running_rows() -> None:
    init()
    insert_run(
        id="run-ghost",
        network_id="n1",
        network_name="Demo",
        started_at=utc_now(),
        outcome="running",
    )
    init()
    row = get_run("run-ghost")
    assert row is not None
    assert row["outcome"] == "cancelled"
    assert row["ended_at"]


def test_purge_keeps_running() -> None:
    init()
    old = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    now = utc_now()
    insert_run(
        id="run-old",
        network_id="n1",
        network_name="Demo",
        started_at=old,
        outcome="succeeded",
    )
    insert_run(
        id="run-live",
        network_id="n1",
        network_name="Demo",
        started_at=old,
        outcome="running",
    )
    insert_run(
        id="run-new",
        network_id="n1",
        network_name="Demo",
        started_at=now,
        outcome="failed",
    )
    deleted = purge_older_than(90)
    assert deleted == 1
    items, _ = list_runs(limit=20)
    ids = {item["id"] for item in items}
    assert "run-live" in ids
    assert "run-new" in ids
    assert "run-old" not in ids


def test_delete_runs_cascade() -> None:
    init()
    insert_run(id="run-x", network_id="n1", network_name="Demo", started_at=utc_now())
    insert_log(run_id="run-x", message="hello", level="info")
    insert_call(run_id="run-x", provider="ollama", model="llama3.2:1b", ok=True)
    upsert_step(run_id="run-x", node_id="llm-1", status="ok")
    assert list_logs("run-x")
    assert list_calls("run-x")
    delete_runs(["run-x"])
    assert list_logs("run-x") == []
    assert list_calls("run-x") == []
    items, total = list_runs()
    assert total == 0
    assert items == []


def test_run_memory_roundtrip() -> None:
    init()
    now = utc_now()
    insert_run(id="run-m", network_id="n1", network_name="Demo", started_at=now)
    update_run("run-m", memory={"turns": [{"role": "user", "kind": "user", "text": "Hallo"}]})
    row = get_run("run-m")
    assert row is not None
    assert row["memory"]["turns"][0]["text"] == "Hallo"
    insert_run(id="run-empty", network_id="n1", network_name="Demo", started_at=now)
    empty = get_run("run-empty")
    assert empty is not None
    assert empty["memory"] is None


def test_history_missing_does_not_block_networks() -> None:
    init()
    upsert_network(
        NetworkRow(
            id="net-1",
            name="Demo",
            description=None,
            tags=[],
            document={"id": "net-1"},
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    close_store("history", state="missing")
    with pytest.raises(StoreUnavailable) as err:
        list_runs()
    assert err.value.message_key == "store.missing"
    assert err.value.store_id == "history"
    assert [row.id for row in list_networks()] == ["net-1"]
