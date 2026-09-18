from __future__ import annotations

import pytest

from app.main import assert_loopback


def test_assert_loopback_exported_from_main() -> None:
    assert_loopback("127.0.0.1")
    with pytest.raises(SystemExit, match="refusing non-loopback bind"):
        assert_loopback("0.0.0.0")
