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


def test_list_includes_used_by_help_chat(client: TestClient) -> None:
    cred_id = _create(client)
    patch = client.patch(
        "/api/settings",
        json={"helpChat": {"credentialId": cred_id}},
    )
    assert patch.status_code == 200
    listed = client.get("/api/credentials").json()["items"]
    item = next(row for row in listed if row["id"] == cred_id)
    assert item["inUse"] is True
    assert "helpChat.llm" in item["usedBy"]


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


def test_credential_list_reads_the_networks_once(client: TestClient, monkeypatch) -> None:
    """N9: the list parsed every network once per credential."""
    import app.db.networks as networks_db

    ids = [_create(client) for _ in range(3)]
    upsert_network(
        NetworkRow(
            id="net-n9",
            name="Uses two",
            description=None,
            tags=[],
            document={"nodes": [{"id": "l", "type": "llm", "data": {"credentialId": ids[0]}},
                                {"id": "m", "type": "mcp", "data": {"credentialIds": [ids[1]]}}]},
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    calls = {"n": 0}
    real = networks_db.list_networks

    def _counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(networks_db, "list_networks", _counting)
    listed = {row["id"]: row for row in client.get("/api/credentials").json()["items"]}
    assert calls["n"] == 1
    assert listed[ids[0]]["usedBy"] == ["network:net-n9:Uses two"]
    assert listed[ids[1]]["usedBy"] == ["network:net-n9:Uses two"]
    assert listed[ids[2]]["inUse"] is False
