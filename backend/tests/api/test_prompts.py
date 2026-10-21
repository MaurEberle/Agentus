"""Prompt library: create, secret stripping on import, export has no id."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_list_and_patch(client: TestClient) -> None:
    created = client.post(
        "/api/prompts",
        json={"name": "Review", "description": "Kurz", "tags": ["code", "code"], "body": "Prüfe den Diff."},
    )
    assert created.status_code == 201
    item = created.json()
    assert item["name"] == "Review"
    assert item["tags"] == ["code"]
    assert item["body"] == "Prüfe den Diff."
    assert item["createdAt"]
    assert item["updatedAt"]

    listed = client.get("/api/prompts")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == item["id"]
    assert "body" not in listed.json()["items"][0]

    renamed = client.patch(f"/api/prompts/{item['id']}", json={"name": "Review v2"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Review v2"
    assert renamed.json()["body"] == "Prüfe den Diff."


def test_import_drops_secret_keys_and_export_has_no_id(client: TestClient) -> None:
    imported = client.post(
        "/api/prompts/import",
        json={
            "items": [
                {
                    "schemaVersion": 1,
                    "kind": "agentus.prompt",
                    "name": "Extern",
                    "body": "Nur der Text.",
                    "apiKey": "should-not-stick",
                    "tags": ["extern"],
                }
            ]
        },
    )
    assert imported.status_code == 201
    saved = imported.json()["items"][0]
    assert saved["name"] == "Extern"
    assert "apiKey" not in saved

    exported = client.get(f"/api/prompts/{saved['id']}/export")
    assert exported.status_code == 200
    body = exported.json()
    assert body["kind"] == "agentus.prompt"
    assert body["schemaVersion"] == 1
    assert "id" not in body
    assert body["body"] == "Nur der Text."


def test_empty_name_rejected(client: TestClient) -> None:
    response = client.post("/api/prompts", json={"name": "  ", "body": "x"})
    assert response.status_code == 400
    assert response.json()["messageKey"] == "prompts.nameRequired"
