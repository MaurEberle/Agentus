from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import init, reset
from app.db.vault import reset_memory, use_memory
from app.http.app import create_app
from app.runtime.models import PingResult


@pytest.fixture
def api_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTUS_NETWORK_VAULT", "memory")
    monkeypatch.delenv("AGENTUS_NETWORK_DEV", raising=False)
    reset()
    use_memory()
    reset_memory()
    def _ping(**_: object) -> PingResult:
        return PingResult(ok=True)

    def _models(**_: object) -> list:
        return []

    monkeypatch.setattr("app.runtime.ping_ollama", _ping)
    monkeypatch.setattr("app.runtime.ollama.ping_ollama", _ping)
    monkeypatch.setattr("app.http.routers.runtime.ping_ollama", _ping)
    monkeypatch.setattr("app.runtime.list_ollama_models", _models)
    monkeypatch.setattr("app.runtime.ollama.list_ollama_models", _models)
    monkeypatch.setattr("app.http.routers.runtime.list_ollama_models", _models)
    yield
    reset()
    reset_memory()


@pytest.fixture
def client(api_env) -> TestClient:
    init()
    return TestClient(create_app())
