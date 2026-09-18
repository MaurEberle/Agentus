from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.network_rag import list_collection_states
from app.db.runs import insert_run, list_runs
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


def test_delete_running_network_409(client: TestClient) -> None:
    created = client.post("/api/networks", json=mini_doc(requireInput=True))
    network_id = created.json()["id"]
    client.put("/api/session/active-network", json={"networkId": network_id})
    start = client.post("/api/run/start")
    assert start.status_code == 200
    response = client.delete(f"/api/networks/{network_id}")
    assert response.status_code == 409
    client.post("/api/run/stop")
