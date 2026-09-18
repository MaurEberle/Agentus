from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.settings import get_settings as db_get_settings
from app.settings.defaults import DEFAULT_OLLAMA_BASE_URL
from app.settings.service import load_settings


def test_get_settings_writes_defaults(client: TestClient) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["ollamaBaseUrl"] == DEFAULT_OLLAMA_BASE_URL
    assert body["helpChat"]["model"] == "llama3.2:1b"
    assert body["helpChat"]["embeddingModel"] == "nomic-embed-text"
    assert db_get_settings() is not None


def test_patch_ollama_url_strips_v1(client: TestClient) -> None:
    response = client.patch(
        "/api/settings",
        json={"ollamaBaseUrl": "http://127.0.0.1:11434/v1/"},
    )
    assert response.status_code == 200
    assert response.json()["ollamaBaseUrl"] == "http://127.0.0.1:11434"


def test_patch_retention_7_is_400(client: TestClient) -> None:
    response = client.patch("/api/settings", json={"historyRetentionDays": 7})
    assert response.status_code == 400
    assert response.json()["messageKey"] == "settings.retention.invalid"


def test_patch_help_chat_model_keeps_rest(client: TestClient) -> None:
    before = client.get("/api/settings").json()["helpChat"]
    response = client.patch("/api/settings", json={"helpChat": {"model": "llama3.2"}})
    assert response.status_code == 200
    help_chat = response.json()["helpChat"]
    assert help_chat["model"] == "llama3.2"
    assert help_chat["provider"] == before["provider"]
    assert help_chat["embeddingModel"] == before["embeddingModel"]


def test_patch_onboarding_seen(client: TestClient) -> None:
    response = client.patch("/api/settings", json={"chatOnboardingSeen": True})
    assert response.status_code == 200
    assert response.json()["chatOnboardingSeen"] is True
    assert client.get("/api/settings").json()["chatOnboardingSeen"] is True


def test_active_network_id_survives_reload(client: TestClient) -> None:
    client.patch("/api/settings", json={"activeNetworkId": "net-keep"})
    reloaded = load_settings()
    assert reloaded.active_network_id == "net-keep"
    stored = db_get_settings()
    assert stored is not None
    assert stored["activeNetworkId"] == "net-keep"
