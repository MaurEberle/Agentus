from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.vault import get as vault_get


def test_create_list_has_mask_no_secret(client: TestClient) -> None:
    secret = "sk-live-secret-value"
    response = client.post(
        "/api/credentials",
        json={"name": "xAI", "kind": "xai", "secret": secret},
    )
    assert response.status_code == 201
    item = response.json()
    assert item["mask"].endswith("alue")
    assert "secret" not in item
    assert secret not in response.text
    listed = client.get("/api/credentials")
    assert listed.status_code == 200
    assert "secret" not in listed.text
    assert secret not in listed.text
    assert listed.json()["items"][0]["inUse"] is False


def test_short_secret_mask(client: TestClient) -> None:
    response = client.post(
        "/api/credentials",
        json={"name": "short", "kind": "token", "secret": "ab"},
    )
    assert response.status_code == 201
    assert response.json()["mask"] == "***"


def test_patch_empty_secret_keeps_vault(client: TestClient) -> None:
    created = client.post(
        "/api/credentials",
        json={"name": "keep", "kind": "token", "secret": "original-secret"},
    ).json()
    cred_id = created["id"]
    before = vault_get(cred_id)
    response = client.patch(f"/api/credentials/{cred_id}", json={"secret": ""})
    assert response.status_code == 200
    assert vault_get(cred_id) == before == "original-secret"
    assert response.json()["mask"] == created["mask"]


def test_delete_unused(client: TestClient) -> None:
    created = client.post(
        "/api/credentials",
        json={"name": "gone", "kind": "token", "secret": "to-delete"},
    ).json()
    cred_id = created["id"]
    response = client.delete(f"/api/credentials/{cred_id}")
    assert response.status_code == 204
    assert vault_get(cred_id) is None
    assert client.get("/api/credentials").json()["items"] == []


def test_delete_unknown_404(client: TestClient) -> None:
    response = client.delete("/api/credentials/missing")
    assert response.status_code == 404
    assert response.json()["messageKey"] == "credentials.notFound"
