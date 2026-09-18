from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.engine import utc_now
from app.db.networks import NetworkRow, upsert_network
from app.settings.service import RunSlice, set_run_slice_provider


def test_session_default_stopped(client: TestClient) -> None:
    response = client.get("/api/session")
    assert response.status_code == 200
    body = response.json()
    assert body["serviceStatus"] == "stopped"
    assert body["activeNetworkId"] is None
    assert "runId" not in body


def test_session_run_hook(client: TestClient) -> None:
    set_run_slice_provider(
        lambda: RunSlice(
            service_status="running",
            run_id="run-1",
            started_at="2026-01-01T00:00:00+00:00",
        )
    )
    body = client.get("/api/session").json()
    assert body["serviceStatus"] == "running"
    assert body["runId"] == "run-1"
    assert body["startedAt"] == "2026-01-01T00:00:00+00:00"


def test_put_unknown_network_404(client: TestClient) -> None:
    response = client.put(
        "/api/session/active-network",
        json={"networkId": "missing"},
    )
    assert response.status_code == 404
    assert response.json()["messageKey"] == "networks.notFound"


def test_put_null_clears_active(client: TestClient) -> None:
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
    set_ok = client.put("/api/session/active-network", json={"networkId": "net-1"})
    assert set_ok.status_code == 200
    assert set_ok.json()["activeNetworkId"] == "net-1"
    assert set_ok.json()["activeNetworkName"] == "Demo"
    cleared = client.put("/api/session/active-network", json={"networkId": None})
    assert cleared.status_code == 200
    assert cleared.json()["activeNetworkId"] is None
    assert "activeNetworkName" not in cleared.json()
