from __future__ import annotations

from app.db.vault import delete, get, put


def test_memory_roundtrip() -> None:
    assert get("missing") is None
    put("cred-1", "sk-secret-value")
    assert get("cred-1") == "sk-secret-value"
    delete("cred-1")
    assert get("cred-1") is None


def test_delete_missing_is_noop() -> None:
    delete("never-existed")
    assert get("never-existed") is None
