"""Network versions (fix/netz-versionen/entwurf.md, 16)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _doc(name: str = "Netz", prompt: str = "Eins") -> dict:
    return {
        "schemaVersion": 1,
        "name": name,
        "nodes": [
            {"id": "chat", "type": "chat_input", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "a", "type": "agent", "position": {"x": 200, "y": 0}, "data": {"systemPrompt": prompt}},
            {"id": "end", "type": "end", "position": {"x": 400, "y": 0}, "data": {}},
        ],
        "edges": [],
    }


def _create(client: TestClient, **kwargs) -> dict:
    response = client.post("/api/networks", json=_doc(**kwargs))
    assert response.status_code == 201, response.text
    return response.json()


def _versions(client: TestClient, network_id: str) -> dict:
    return client.get(f"/api/networks/{network_id}/versions").json()


def test_saving_creates_versions_only_for_new_content(client: TestClient) -> None:
    created = _create(client)
    assert (created["version"], created["revision"]) == (1, 1)
    changed = client.put(f"/api/networks/{created['id']}", json={**created, **_doc(prompt="Zwei")}).json()
    assert (changed["version"], changed["revision"]) == (2, 2)
    same = client.put(f"/api/networks/{created['id']}", json=changed).json()
    assert (same["version"], same["revision"]) == (2, 3)
    listed = _versions(client, created["id"])
    assert [item["version"] for item in listed["items"]] == [2, 1]
    assert [item["source"] for item in listed["items"]] == ["editor", "create"]


def test_saving_without_a_new_version_overwrites_the_current_one(client: TestClient) -> None:
    created = _create(client)
    response = client.put(
        f"/api/networks/{created['id']}?newVersion=false&note=Feinschliff", json={**created, **_doc(prompt="Neu")}
    )
    assert (response.json()["version"], response.json()["revision"]) == (1, 2)
    stored = client.get(f"/api/networks/{created['id']}/versions/1").json()
    assert stored["document"]["nodes"][1]["data"]["systemPrompt"] == "Neu"
    assert stored["note"] == "Feinschliff"


def test_a_stale_revision_is_a_conflict_and_changes_nothing(client: TestClient) -> None:
    created = _create(client)
    network_id = created["id"]
    # The other writer saves without a new version: the version number stays, the revision moves.
    client.put(f"/api/networks/{network_id}?newVersion=false", json={**created, **_doc(prompt="Andere")})
    stale = client.put(f"/api/networks/{network_id}?baseRevision=1", json={**created, **_doc(prompt="Meine")})
    assert stale.status_code == 409
    assert stale.json() == {"messageKey": "networks.conflict", "version": 1, "revision": 2}
    current = client.get(f"/api/networks/{network_id}").json()
    assert current["nodes"][1]["data"]["systemPrompt"] == "Andere"
    fresh = client.put(f"/api/networks/{network_id}?baseRevision=2", json={**created, **_doc(prompt="Meine")})
    assert fresh.status_code == 200 and fresh.json()["version"] == 2


def test_rename_and_tags_change_the_current_version(client: TestClient) -> None:
    created = _create(client)
    renamed = client.patch(f"/api/networks/{created['id']}", json={"name": "Umbenannt", "tags": ["x"]})
    assert renamed.status_code == 200
    listed = _versions(client, created["id"])
    assert (listed["version"], listed["revision"]) == (1, 2)
    assert client.get(f"/api/networks/{created['id']}/versions/1").json()["document"]["name"] == "Umbenannt"


def test_restore_adds_a_new_version(client: TestClient) -> None:
    created = _create(client)
    network_id = created["id"]
    client.put(f"/api/networks/{network_id}", json={**created, **_doc(prompt="Zwei")})
    restored = client.post(f"/api/networks/{network_id}/versions/1/restore", json={"baseRevision": 2})
    assert restored.status_code == 200
    assert restored.json()["version"] == 3 and restored.json()["nodes"][1]["data"]["systemPrompt"] == "Eins"
    newest = _versions(client, network_id)["items"][0]
    assert (newest["source"], newest["restoredFrom"]) == ("restore", 1)
    stale = client.post(f"/api/networks/{network_id}/versions/1/restore", json={"baseRevision": 2})
    assert stale.status_code == 409


def test_pruning_keeps_the_newest_plus_first_pinned_and_current(client: TestClient) -> None:
    assert client.patch("/api/settings", json={"networkVersionsKeep": 5}).status_code == 200
    assert client.patch("/api/settings", json={"networkVersionsKeep": 4}).status_code == 400
    created = _create(client)
    network_id = created["id"]
    doc = created
    for index in range(2, 5):
        doc = client.put(f"/api/networks/{network_id}", json={**doc, **_doc(prompt=f"V{index}")}).json()
    assert client.patch(f"/api/networks/{network_id}/versions/2", json={"pinned": True}).json()["pinned"] is True
    for index in range(5, 12):
        doc = client.put(f"/api/networks/{network_id}", json={**doc, **_doc(prompt=f"V{index}")}).json()
    kept = [item["version"] for item in _versions(client, network_id)["items"]]
    assert kept == [11, 10, 9, 8, 7, 2, 1]


def test_delete_and_duplicate(client: TestClient) -> None:
    created = _create(client)
    copy = client.post(f"/api/networks/{created['id']}/duplicate").json()
    first = _versions(client, copy["id"])["items"]
    assert [(item["version"], item["source"]) for item in first] == [(1, "duplicate")]
    client.request("DELETE", "/api/networks", json={"ids": [created["id"]]})
    assert client.get(f"/api/networks/{created['id']}/versions").status_code == 404


def test_diff_and_copy_of_a_version(client: TestClient) -> None:
    created = _create(client)
    network_id = created["id"]
    client.put(f"/api/networks/{network_id}", json={**created, **_doc(prompt="Zwei")})
    compared = client.get(f"/api/networks/{network_id}/versions/1/diff").json()
    assert (compared["version"], compared["current"]) == (1, 2)
    assert compared["diff"]["changed"] == [{"id": "a", "fields": ["systemPrompt"]}]
    copy = client.post(f"/api/networks/{network_id}/versions/1/copy", json={"name": "Netz von gestern"})
    assert copy.status_code == 201
    copied = copy.json()
    assert copied["name"] == "Netz von gestern" and copied["id"] != network_id
    assert copied["nodes"][1]["data"]["systemPrompt"] == "Eins"
    first = _versions(client, copied["id"])["items"][0]
    assert (first["source"], first["note"]) == ("duplicate", "Netz · 1")


def test_a_run_knows_its_version_and_can_be_restored(client: TestClient) -> None:
    from app.db.runs import insert_run

    created = _create(client)
    network_id = created["id"]
    snapshot = client.get(f"/api/networks/{network_id}").json()
    insert_run(id="run-1", network_id=network_id, network_name="Netz", started_at="2026-11-20T10:00:00Z", graph_snapshot=snapshot)
    client.put(f"/api/networks/{network_id}", json={**created, **_doc(prompt="Zwei")})
    detail = client.get("/api/runs/run-1").json()
    assert (detail["networkExists"], detail["networkVersion"]) == (True, 1)
    stale = client.post(f"/api/networks/{network_id}/restore-run", json={"runId": "run-1", "baseRevision": 1})
    assert stale.status_code == 409
    restored = client.post(f"/api/networks/{network_id}/restore-run", json={"runId": "run-1", "baseRevision": 2}).json()
    assert restored["version"] == 3 and restored["nodes"][1]["data"]["systemPrompt"] == "Eins"
    newest = _versions(client, network_id)["items"][0]
    assert (newest["source"], newest["restoredFrom"]) == ("restore", 1)
    missing = client.post(f"/api/networks/{network_id}/restore-run", json={"runId": "gibt-es-nicht"})
    assert missing.status_code == 404
