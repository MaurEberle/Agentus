from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import init, reset
from app.db.vault import reset_memory, use_memory
from app.http.app import create_app
from app.mcp import register_hooks
from app.mcp.sessions import SESSIONS
from app.settings.in_use import reset_mcp_usage_provider
from app.tools.catalog import reset_mcp_catalog_provider


@pytest.fixture
def api_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTUS_NETWORK_VAULT", "memory")
    reset()
    use_memory()
    reset_memory()
    reset_mcp_catalog_provider()
    reset_mcp_usage_provider()
    SESSIONS.close_all()
    yield tmp_path
    SESSIONS.close_all()
    reset_mcp_catalog_provider()
    reset_mcp_usage_provider()
    reset()
    reset_memory()


@pytest.fixture
def client(api_env) -> TestClient:
    init()
    register_hooks()
    return TestClient(create_app())
