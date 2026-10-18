from __future__ import annotations

from fastapi.testclient import TestClient

from tests.run.conftest import mini_doc


def _with_secret() -> dict:
    doc = mini_doc()
    doc["nodes"][1]["data"]["token"] = "secret-value"
    doc["nodes"][1]["data"]["credentialId"] = "cred-1"
    doc["nodes"][1]["data"]["headers"] = {"api_key": "abc", "X-Trace": "ok"}
    return doc


def _llm(body: dict) -> dict:
    return next(node for node in body["nodes"] if node["id"] == "llm")


def test_export_strips_secrets_and_omits_the_network_id(client: TestClient) -> None:
    created = client.post("/api/networks", json=_with_secret())
    assert created.status_code == 201
    network_id = created.json()["id"]

    exported = client.get(f"/api/networks/{network_id}/export")
    assert exported.status_code == 200
    body = exported.json()
    assert body["schemaVersion"] == 1
    assert "exportedAt" in body
    assert "id" not in body
    data = _llm(body)["data"]
    assert "token" not in data
    assert data["credentialId"] == "cred-1"
    assert data["headers"] == {"X-Trace": "ok"}

    stored = client.get(f"/api/networks/{network_id}")
    assert _llm(stored.json())["data"]["token"] == "secret-value"


def test_import_creates_a_new_network_without_secrets(client: TestClient) -> None:
    created = client.post("/api/networks", json=_with_secret())
    network_id = created.json()["id"]
    exported = client.get(f"/api/networks/{network_id}/export").json()
    exported["nodes"][1]["data"]["password"] = "again"

    imported = client.post("/api/networks/import", json={"document": exported})
    assert imported.status_code == 201
    body = imported.json()
    assert body["id"] != network_id
    assert body["name"] == "mini"
    assert "exportedAt" not in body
    data = _llm(body)["data"]
    assert "token" not in data
    assert "password" not in data
    assert data["credentialId"] == "cred-1"


def test_preview_export_does_not_store(client: TestClient) -> None:
    before = client.get("/api/networks").json()["items"]
    doc = mini_doc()
    doc["nodes"].append(
        {
            "id": "m",
            "type": "tool",
            "position": {"x": 1, "y": 2},
            "data": {"kind": "mcp", "mcpServerId": "git", "token": "nope"},
        }
    )
    response = client.post("/api/networks/export", json=doc)
    assert response.status_code == 200
    after = client.get("/api/networks").json()["items"]
    assert len(after) == len(before)
    body = response.json()
    assert "id" not in body
    node = next(item for item in body["nodes"] if item["id"] == "m")
    assert node["type"] == "mcp"
    assert "kind" not in node["data"]
    assert "token" not in node["data"]
    assert node["data"]["mcpServerId"] == "git"


def test_import_rejects_a_foreign_schema(client: TestClient) -> None:
    response = client.post(
        "/api/networks/import",
        json={"document": {"schemaVersion": 2, "nodes": [], "edges": []}},
    )
    assert response.status_code == 400
    assert response.json()["messageKey"] == "networks.import.schema"


def test_import_rejects_a_file_that_is_not_a_network(client: TestClient) -> None:
    response = client.post("/api/networks/import", json={"document": {}})
    assert response.status_code == 400
    assert response.json()["messageKey"] == "networks.import.unreadable"
