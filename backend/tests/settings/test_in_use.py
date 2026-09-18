from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.engine import utc_now
from app.db.networks import NetworkRow, upsert_network
from app.settings.in_use import set_mcp_usage_provider


def _create(client: TestClient) -> str:
    return client.post(
        "/api/credentials",
        json={"name": "used", "kind": "xai", "secret": "secret-value"},
    ).json()["id"]


def test_help_chat_credential_blocks_delete(client: TestClient) -> None:
    cred_id = _create(client)
    patch = client.patch(
        "/api/settings",
        json={"helpChat": {"credentialId": cred_id}},
    )
    assert patch.status_code == 200
    response = client.delete(f"/api/credentials/{cred_id}")
    assert response.status_code == 409
    body = response.json()
    assert body["messageKey"] == "credentials.inUse"
    assert "helpChat.llm" in body["message"]
    assert "secret-value" not in response.text


def test_network_document_credential_blocks_delete(client: TestClient) -> None:
    cred_id = _create(client)
    upsert_network(
        NetworkRow(
            id="net-1",
            name="Demo",
            description=None,
            tags=[],
            document={
                "id": "net-1",
                "nodes": [{"id": "n1", "data": {"credentialId": cred_id}}],
            },
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    response = client.delete(f"/api/credentials/{cred_id}")
    assert response.status_code == 409
    assert response.json()["messageKey"] == "credentials.inUse"
    assert "network:net-1:Demo" in response.json()["message"]


def test_mcp_hook_blocks_delete(client: TestClient) -> None:
    cred_id = _create(client)
    set_mcp_usage_provider(
        lambda cid: ["mcp:github"] if cid == cred_id else []
    )
    response = client.delete(f"/api/credentials/{cred_id}")
    assert response.status_code == 409
    assert response.json()["message"] == "mcp:github"
