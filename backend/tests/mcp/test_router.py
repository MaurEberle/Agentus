from __future__ import annotations

from fastapi.testclient import TestClient

from tests.mcp.fakes import FakeSession


def test_recipes_endpoint(client: TestClient) -> None:
    response = client.get("/api/mcp/recipes")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert "github" in ids
    assert "filesystem" in ids
    assert len(ids) == 19


def test_create_list_delete(client: TestClient) -> None:
    created = client.post("/api/mcp/servers", json={"recipeId": "github"})
    assert created.status_code == 201
    body = created.json()
    assert body["enabled"] is False
    assert "secret" not in body
    listed = client.get("/api/mcp/servers")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == body["id"]
    deleted = client.delete(f"/api/mcp/servers/{body['id']}")
    assert deleted.status_code == 204


def test_ping_filesystem_runtime_missing(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.mcp.service.runtime_available", lambda runtime: False
    )
    created = client.post("/api/mcp/servers", json={"recipeId": "filesystem"})
    server_id = created.json()["id"]
    ping = client.post(f"/api/mcp/servers/{server_id}/ping")
    assert ping.status_code == 200
    assert ping.json()["status"] == "runtime_missing"
    assert ping.json()["messageKey"] == "mcp.runtime.missing"


def test_enable_filesystem_without_root(client: TestClient) -> None:
    created = client.post("/api/mcp/servers", json={"recipeId": "filesystem"})
    server_id = created.json()["id"]
    response = client.post(
        f"/api/mcp/servers/{server_id}/enabled", json={"enabled": True}
    )
    assert response.status_code == 400
    assert response.json()["messageKey"] == "mcp.root.required"


def test_ping_ok_with_fake(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.mcp.service.runtime_available", lambda runtime: True)
    monkeypatch.setattr(
        "app.mcp.sessions.connect_transport", lambda **k: FakeSession()
    )
    created = client.post("/api/mcp/servers", json={"recipeId": "github"})
    server_id = created.json()["id"]
    ping = client.post(f"/api/mcp/servers/{server_id}/ping")
    assert ping.status_code == 200
    assert ping.json()["status"] == "ok"
