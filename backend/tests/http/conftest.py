from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import init, reset
from app.db.vault import reset_memory, use_memory
from app.http.app import create_app


@pytest.fixture
def api_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTUS_NETWORK_VAULT", "memory")
    monkeypatch.delenv("AGENTUS_NETWORK_DEV", raising=False)
    monkeypatch.delenv("AGENTUS_NETWORK_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("AGENTUS_NETWORK_STATIC_DIR", raising=False)
    reset()
    use_memory()
    reset_memory()
    yield
    reset()
    reset_memory()


@pytest.fixture
def client(api_env) -> TestClient:
    init()
    return TestClient(create_app())
