from __future__ import annotations

from datetime import datetime

from app.tools.execute import execute_first_party


def test_utc() -> None:
    result = execute_first_party("datetime", args={"timezone": "UTC"})
    assert result.ok is True
    assert result.result["timezone"] == "UTC"
    parsed = datetime.fromisoformat(result.result["iso"])
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_invalid_zone() -> None:
    result = execute_first_party("datetime", args={"timezone": "Not/AZone"})
    assert result.ok is False
    assert result.error_key == "tools.datetime.invalidTimezone"
