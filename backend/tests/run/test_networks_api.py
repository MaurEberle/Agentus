from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.network_rag import list_collection_states
from app.db.networks import touch_network
from app.db.runs import delete_runs, insert_run, list_runs
from app.db.engine import utc_now
from tests.run.conftest import mini_doc


def test_delete_network_keeps_history(client: TestClient) -> None:
    created = client.post("/api/networks", json=mini_doc())
    assert created.status_code == 201
    network_id = created.json()["id"]
    insert_run(
        id="run-keep",
        network_id=network_id,
        network_name="mini",
        started_at=utc_now(),
        outcome="succeeded",
    )
    deleted = client.delete(f"/api/networks/{network_id}")
    assert deleted.status_code == 204
    assert list_collection_states(network_id) == []
    items, total = list_runs()
    assert total == 1
    assert items[0]["id"] == "run-keep"


def test_list_last_run_is_the_newest_run_that_still_exists(client: TestClient) -> None:
    created = client.post("/api/networks", json=mini_doc())
    assert created.status_code == 201
    network_id = created.json()["id"]
    insert_run(
        id="run-old",
        network_id=network_id,
        network_name="mini",
        started_at="2026-01-01T00:00:00+00:00",
        outcome="succeeded",
    )
    insert_run(
        id="run-new",
        network_id=network_id,
        network_name="mini",
        started_at="2026-02-01T00:00:00+00:00",
        outcome="succeeded",
    )
    touch_network(network_id, last_run_id="run-deleted")
    listed = client.get("/api/networks")
    assert listed.status_code == 200
    item = next(row for row in listed.json()["items"] if row["id"] == network_id)
    assert item["lastRunId"] == "run-new"
    delete_runs(["run-new"])
    again = client.get("/api/networks")
    item = next(row for row in again.json()["items"] if row["id"] == network_id)
    assert item["lastRunId"] == "run-old"
    delete_runs(["run-old"])
    gone = client.get("/api/networks")
    item = next(row for row in gone.json()["items"] if row["id"] == network_id)
    assert item["lastRunId"] is None


def test_the_list_says_whether_a_network_has_an_orchestrator(client: TestClient) -> None:
    """The management list shows and filters "orchestrator" or "linear" instead of node counts."""
    from tests.run.test_validate import _orchestrator_doc

    linear = client.post("/api/networks", json=mini_doc()).json()["id"]
    chief = client.post("/api/networks", json={**_orchestrator_doc(), "name": "chief"}).json()["id"]
    kinds = {row["id"]: row["kind"] for row in client.get("/api/networks").json()["items"]}
    assert kinds[linear] == "linear" and kinds[chief] == "orchestrator"


def test_delete_running_network_409(client: TestClient) -> None:
    created = client.post("/api/networks", json=mini_doc(requireInput=True))
    network_id = created.json()["id"]
    client.put("/api/session/active-network", json={"networkId": network_id})
    start = client.post("/api/run/start")
    assert start.status_code == 200
    response = client.delete(f"/api/networks/{network_id}")
    assert response.status_code == 409
    client.post("/api/run/stop")


def test_validate_an_unsaved_network(client: TestClient) -> None:
    """M24: "Validate" on a network without an id hit a route that did not exist."""
    ok = client.post("/api/networks/validate", json=mini_doc())
    assert ok.status_code == 200
    assert ok.json()["valid"] is True
    broken = mini_doc()
    broken["nodes"] = [node for node in broken["nodes"] if node["type"] != "end"]
    response = client.post("/api/networks/validate", json=broken)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"]
