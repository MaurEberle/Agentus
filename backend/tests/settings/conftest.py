from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import init, reset
from app.db.vault import reset_memory, use_memory
from app.http.app import create_app
from app.settings.in_use import reset_mcp_usage_provider
from app.settings.service import reset_run_slice_provider


@pytest.fixture
def api_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTUS_NETWORK_VAULT", "memory")
    monkeypatch.delenv("AGENTUS_NETWORK_DEV", raising=False)
    monkeypatch.delenv("AGENTUS_NETWORK_DATA_DIR", raising=False)
    reset()
    use_memory()
    reset_memory()
    reset_mcp_usage_provider()
    reset_run_slice_provider()
    yield
    reset_mcp_usage_provider()
    reset_run_slice_provider()
    reset()
    reset_memory()


@pytest.fixture
def client(api_env) -> TestClient:
    init()
    return TestClient(create_app())
