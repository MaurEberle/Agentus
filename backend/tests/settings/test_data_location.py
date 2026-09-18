from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.settings.service import RunSlice, set_run_slice_provider


def test_get_data_location(client: TestClient) -> None:
    response = client.get("/api/data-location")
    assert response.status_code == 200
    body = response.json()
    assert "dataDir" in body
    assert body["source"] in {"default", "config"}
    ids = {item["id"] for item in body["stores"]}
    assert ids == {"settings", "help", "workspace", "history"}


def test_post_busy_is_409(client: TestClient) -> None:
    set_run_slice_provider(lambda: RunSlice(service_status="running"))
    response = client.post(
        "/api/data-location",
        json={"path": str(Path("C:/tmp/agentus-data")), "copy": False},
    )
    assert response.status_code == 409
    assert response.json()["messageKey"] == "dataDir.busy"


def test_post_drive_root_is_400(client: TestClient) -> None:
    response = client.post("/api/data-location", json={"path": "C:\\"})
    assert response.status_code == 400
    assert response.json()["messageKey"] == "dataDir.invalidPath"


def test_post_copy_false_new_folder(client: TestClient, tmp_path: Path) -> None:
    dest = tmp_path / "new-data"
    response = client.post(
        "/api/data-location",
        json={"path": str(dest), "copy": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert Path(body["dataDir"]) == dest.resolve()
    assert (dest / "settings.sqlite").is_file()
