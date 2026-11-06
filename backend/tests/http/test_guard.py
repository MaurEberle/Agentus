from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.http.app import create_app
from app.http.guard import host_allowed, origin_allowed


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
    client = TestClient(create_app(), base_url="http://127.0.0.1")
    response = client.get("/api/health", headers={"Origin": "http://127.0.0.1:8765"})
    assert response.status_code == 200
