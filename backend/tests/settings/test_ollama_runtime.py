from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.settings import put_settings as db_put_settings
from app.runtime.ollama_own import OwnOllama, set_own_for_tests
from app.settings.service import RunSlice, load_settings, set_run_slice_provider


@pytest.fixture(autouse=True)
def _own_instance(tmp_path: Path):
    own = OwnOllama(tmp_path / "runtime", find=lambda: None, fallback=lambda: None, port=lambda: 45678)
    set_own_for_tests(own)
    yield own
    set_own_for_tests(None)


def test_new_settings_use_the_own_runtime(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert body["ollamaRuntime"] == "own"


@pytest.mark.parametrize(
    ("base_url", "mode"),
    [
        ("http://127.0.0.1:11434", "own"),
        ("http://localhost:11434/", "own"),
        ("http://192.168.1.20:11434", "external"),
        ("http://127.0.0.1:12000", "external"),
    ],
)
def test_older_settings_keep_a_custom_ollama_address(client: TestClient, base_url: str, mode: str) -> None:
    raw = client.get("/api/settings").json()
    raw.pop("ollamaRuntime")
    raw["ollamaBaseUrl"] = base_url
    db_put_settings(raw)
    assert load_settings().ollama_runtime == mode


def test_mode_change_is_saved_and_needs_a_restart(client: TestClient, _own_instance: OwnOllama) -> None:
    _own_instance.begin("own")
    response = client.patch("/api/settings", json={"ollamaRuntime": "external"})
    assert response.status_code == 200
    assert response.json()["ollamaRuntime"] == "external"
    status = client.get("/api/runtime/ollama").json()
    assert status["mode"] == "own"
    assert status["configuredMode"] == "external"
    assert status["restartRequired"] is True
    assert client.patch("/api/settings", json={"ollamaRuntime": "docker"}).status_code in (400, 422)


def test_status_reports_the_own_copy(client: TestClient, _own_instance: OwnOllama) -> None:
    _own_instance.begin("own")
    body = client.get("/api/runtime/ollama").json()
    assert body["mode"] == "own"
    assert body["state"] == "preparing"
    assert body["baseUrl"] == "http://127.0.0.1:45678"
    assert body["restartRequired"] is False
    assert body["canRestart"] is False
    assert body["runBusy"] is False


def test_update_is_refused_while_a_run_is_active(client: TestClient, _own_instance: OwnOllama) -> None:
    _own_instance.begin("own")
    set_run_slice_provider(lambda: RunSlice(service_status="running"))
    response = client.post("/api/runtime/ollama/update")
    assert response.status_code == 409
    assert response.json()["messageKey"] == "runtime.own.busy"


def test_update_in_external_mode_is_refused(client: TestClient, _own_instance: OwnOllama) -> None:
    _own_instance.begin("external")
    response = client.post("/api/runtime/ollama/update")
    assert response.status_code == 409
    assert response.json()["messageKey"] == "runtime.own.notActive"


def test_restart_is_refused_while_a_run_is_active(client: TestClient) -> None:
    set_run_slice_provider(lambda: RunSlice(service_status="running"))
    response = client.post("/api/app/restart")
    assert response.status_code == 409
    assert response.json()["messageKey"] == "app.restart.busy"


def test_restart_without_a_window_reports_false(client: TestClient) -> None:
    response = client.post("/api/app/restart")
    assert response.status_code == 200
    assert response.json() == {"restart": False}
