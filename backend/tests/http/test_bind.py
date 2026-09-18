from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.http.app import create_app
from app.main import assert_loopback


def test_assert_loopback_rejects_wildcard() -> None:
    with pytest.raises(SystemExit, match="0.0.0.0"):
        assert_loopback("0.0.0.0")
    with pytest.raises(SystemExit):
        assert_loopback("*")
    with pytest.raises(SystemExit):
        assert_loopback("::")


def test_assert_loopback_allows_local() -> None:
    assert_loopback("127.0.0.1")
    assert_loopback("localhost")
    assert_loopback("::1")


def test_cors_dev_allows_vite(api_env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTUS_NETWORK_DEV", "1")
    client = TestClient(create_app())
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_prod_rejects_foreign_origin(api_env) -> None:
    client = TestClient(create_app())
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") in {None, ""}
