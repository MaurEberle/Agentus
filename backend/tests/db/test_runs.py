from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db import init
from app.db.engine import close_store, utc_now
from app.db.errors import StoreUnavailable
from app.db.networks import NetworkRow, list_networks, upsert_network
from app.db.runs import (
    delete_runs,
    insert_call,
    insert_log,
    insert_run,
    list_calls,
    list_logs,
    list_runs,
    purge_older_than,
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
