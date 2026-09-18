from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.engine import utc_now
from app.db.runs import insert_run


def test_list_limit(client: TestClient) -> None:
    for i in range(8):
        insert_run(
            id=f"r-{i}",
            network_id="n",
            network_name="n",
            started_at=utc_now(),
            outcome="succeeded",
        )
    response = client.get("/api/runs?limit=5")
    assert response.status_code == 200
    assert len(response.json()["items"]) <= 5


def test_delete_running_forbidden(client: TestClient) -> None:
    insert_run(
        id="run-live",
        network_id="n",
        network_name="n",
        started_at=utc_now(),
        outcome="running",
    )
    response = client.request("DELETE", "/api/runs", json={"ids": ["run-live"]})
    assert response.status_code == 409
