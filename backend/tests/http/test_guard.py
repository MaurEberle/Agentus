from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.http.app import create_app
from app.http.guard import fetch_site_allowed, host_allowed, origin_allowed


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("127.0.0.1:8765", True),
        ("localhost:5173", True),
        ("[::1]:8765", True),
        ("LOCALHOST", True),
        ("evil.example:8765", False),
        ("127.0.0.1.evil.example", False),
        ("", False),
        (None, False),
    ],
)
def test_host_allowed(value: str | None, ok: bool) -> None:
    assert host_allowed(value) is ok


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        (None, True),
        ("http://127.0.0.1:8765", True),
        ("http://localhost:5173", True),
        ("https://evil.example", False),
        ("null", False),
        ("file://", False),
    ],
)
def test_origin_allowed(value: str | None, ok: bool) -> None:
    assert origin_allowed(value) is ok


def test_rebinding_host_rejected() -> None:
    client = TestClient(create_app(), base_url="http://evil.example:8765")
    response = client.get("/api/health")
    assert response.status_code == 403
    assert response.json() == {"messageKey": "http.forbiddenHost"}


def test_cross_site_origin_rejected() -> None:
    client = TestClient(create_app(), base_url="http://127.0.0.1")
    response = client.post("/api/run/stop", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert response.json() == {"messageKey": "http.forbiddenOrigin"}


def test_loopback_origin_allowed() -> None:
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    response = client.get("/api/health", headers={"Origin": "http://127.0.0.1:8765"})
    assert response.status_code == 200


def test_other_local_port_is_another_program() -> None:
    """M21: any page on localhost:3000 used to reach /api/run/stop."""
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    response = client.post("/api/run/stop", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 403
    assert response.json() == {"messageKey": "http.forbiddenOrigin"}


def test_own_origin_under_another_loopback_name_is_allowed() -> None:
    assert origin_allowed("http://localhost:8765", "127.0.0.1:8765") is True
    assert origin_allowed("http://127.0.0.1:5173", "127.0.0.1:8765") is False
    assert origin_allowed("http://127.0.0.1:5173", "127.0.0.1:8765", {"http://127.0.0.1:5173"}) is True


def test_dev_origin_passes_with_the_dev_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTUS_NETWORK_DEV", "1")
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200


def test_cross_site_get_without_origin_is_refused() -> None:
    """An <img> on a foreign page sends no Origin, but Sec-Fetch-Site: cross-site."""
    client = TestClient(create_app(), base_url="http://127.0.0.1:8765")
    response = client.get("/api/runtime/models", headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403
    assert fetch_site_allowed("same-origin") is True
    assert fetch_site_allowed(None) is True
