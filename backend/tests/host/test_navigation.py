from __future__ import annotations

from app.host.navigation import is_allowed_url


def test_loopback_ok() -> None:
    assert is_allowed_url("http://127.0.0.1:8765/", 8765) is True
    assert is_allowed_url("http://localhost:8765/dashboard", 8765) is True
    assert is_allowed_url("about:blank", 8765) is True


def test_rejects_foreign_and_file() -> None:
    assert is_allowed_url("https://evil.test/", 8765) is False
    assert is_allowed_url("file:///C:/x", 8765) is False
    assert is_allowed_url("http://127.0.0.1:9999/", 8765) is False
