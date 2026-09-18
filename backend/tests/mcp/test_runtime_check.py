from __future__ import annotations

from app.mcp.runtime_check import runtime_available


def test_none_is_available() -> None:
    assert runtime_available("none") is True


def test_unknown_runtime_false() -> None:
    assert runtime_available("cobol") is False
