from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.architect import loop
from app.architect import session as sessions
from app.db import init, reset
from app.db.vault import reset_memory, use_memory
from app.http.app import create_app


@pytest.fixture
def api_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTUS_NETWORK_VAULT", "memory")
    monkeypatch.delenv("AGENTUS_NETWORK_DEV", raising=False)
    reset()
    use_memory()
    reset_memory()
    sessions.reset_for_tests()
    # No real Ollama: unloading is a no-op, the idle watcher stays off.
    monkeypatch.setattr("app.runtime.ollama.unload", lambda *a, **k: None)
    monkeypatch.setattr(sessions, "_ensure_watcher", lambda: None)
    yield tmp_path
    loop.set_streamer(None)
    sessions.reset_for_tests()
    reset()
    reset_memory()


@pytest.fixture
def client(api_env) -> TestClient:
    init()
    return TestClient(create_app(), base_url="http://127.0.0.1")
