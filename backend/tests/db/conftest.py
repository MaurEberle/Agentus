from __future__ import annotations

import pytest

from app.db.engine import reset
from app.db.vault import reset_memory, use_memory


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTUS_NETWORK_VAULT", "memory")
    monkeypatch.delenv("AGENTUS_NETWORK_DATA_DIR", raising=False)
    reset()
    use_memory()
    reset_memory()
    yield
    reset()
    reset_memory()
