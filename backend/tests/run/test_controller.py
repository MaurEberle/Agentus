from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.db.networks import NetworkRow, upsert_network
from app.db.engine import utc_now
from app.run.controller import get_controller
from app.run.help_bridge import get_help_degraded
from app.settings.models import AppSettingsPatch
from app.settings.service import is_run_busy, patch_settings
from tests.run.conftest import mini_doc, unloads


def _save_mini(active: bool = True, **chat: object) -> str:
    doc = mini_doc(**chat)
    upsert_network(
        NetworkRow(
            id="net-1",
            name="mini",
            description=None,
            tags=[],
            document=doc,
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    if active:
        patch_settings(AppSettingsPatch(active_network_id="net-1"))
    return "net-1"


def test_start_without_active(client: TestClient) -> None:
    response = client.post("/api/run/start")
    assert response.status_code == 409
    assert response.json()["messageKey"] == "run.noActiveNetwork"


def test_start_succeeds_and_teardown_unloads(client: TestClient) -> None:
    _save_mini(startMessage="go")
    response = client.post("/api/run/start")
    assert response.status_code == 200
    run_id = response.json()["runId"]
    thread = get_controller().thread
    if thread:
        thread.join(timeout=5)
    time.sleep(0.05)
    listed = client.get("/api/runs")
    items = listed.json()["items"]
    assert items[0]["id"] == run_id
    assert items[0]["outcome"] == "succeeded"
    assert unloads  # teardown unload called
    assert get_help_degraded() is False


def test_run_persists_logs_steps_and_chat(client: TestClient) -> None:
    _save_mini(startMessage="go")
    response = client.post("/api/run/start")
    assert response.status_code == 200
    run_id = response.json()["runId"]
    thread = get_controller().thread
    if thread:
        thread.join(timeout=5)
    time.sleep(0.05)
    logs = client.get(f"/api/runs/{run_id}/logs").json()["items"]
    messages = [row["message"] for row in logs]
    assert "run.start" in messages
    assert "run.chat.user" in messages
    assert "run.llm.start" in messages
    assert "run.agent.done" in messages
    assert "run.succeeded" in messages
    assert any(row.get("nodeId") for row in logs)
    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["steps"]
    assert detail["calls"]
    assert detail["chat"]


def test_start_busy(client: TestClient) -> None:
    _save_mini(requireInput=True)
    first = client.post("/api/run/start")
    assert first.status_code == 200
    second = client.post("/api/run/start")
    assert second.status_code == 409
    assert second.json()["messageKey"] == "run.busy"
    assert is_run_busy() is True
    client.post("/api/run/stop")


def test_stop_while_waiting(client: TestClient) -> None:
    _save_mini(requireInput=True)
    client.post("/api/run/start")
    assert get_help_degraded() is True
    stop = client.post("/api/run/stop")
    assert stop.status_code == 200
    assert stop.json()["serviceStatus"] == "stopped"
    listed = client.get("/api/runs").json()["items"]
    assert listed[0]["outcome"] == "cancelled"
    assert get_help_degraded() is False


def test_chat_without_chat_input(client: TestClient) -> None:
    doc = mini_doc()
    doc["nodes"] = [n for n in doc["nodes"] if n["id"] != "in"]
    doc["edges"] = [e for e in doc["edges"] if e["source"] != "in"]
    upsert_network(
        NetworkRow(
            id="net-1",
            name="batch",
            description=None,
            tags=[],
            document=doc,
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    patch_settings(AppSettingsPatch(active_network_id="net-1"))
    start = client.post("/api/run/start")
    assert start.status_code == 200
    chat = client.post("/api/run/chat", json={"text": "hi"})
    assert chat.status_code == 409
    get_controller().thread and get_controller().thread.join(timeout=5)
    client.post("/api/run/stop")


def test_data_location_busy(client: TestClient) -> None:
    _save_mini(requireInput=True)
    client.post("/api/run/start")
    response = client.post("/api/data-location", json={"path": "C:/tmp/x", "copy": False})
    assert response.status_code == 409
    assert response.json()["messageKey"] == "dataDir.busy"
    client.post("/api/run/stop")
