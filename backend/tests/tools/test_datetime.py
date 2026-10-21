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


def test_add_and_diff() -> None:
    added = execute_first_party(
        "datetime",
        args={"action": "add", "at": "2026-01-01T00:00:00", "timezone": "UTC", "days": 1, "hours": -3},
    )
    assert added.ok is True
    assert added.result["iso"] == "2026-01-01T21:00:00+00:00"
    diff = execute_first_party(
        "datetime",
        args={
            "action": "diff",
            "timezone": "UTC",
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-01T02:30:00Z",
        },
    )
    assert diff.ok is True
    assert diff.result["seconds"] == 9000
    assert diff.result["hours"] == 2.5


def test_parts_and_convert() -> None:
    parts = execute_first_party(
        "datetime",
        args={"action": "parts", "at": "2026-10-18T15:04:00", "timezone": "UTC"},
    )
    assert parts.ok is True
    assert parts.result["weekday"] == "Sunday"
    assert parts.result["weekdayIndex"] == 7
    assert parts.result["year"] == 2026
    assert parts.result["hour"] == 15
    converted = execute_first_party(
        "datetime",
        args={
            "action": "convert",
            "at": "2026-01-15T12:00:00Z",
            "timezone": "UTC",
            "toTimezone": "Europe/Berlin",
        },
    )
    assert converted.ok is True
    assert converted.result["iso"] == "2026-01-15T13:00:00+01:00"
    assert converted.result["timezone"] == "Europe/Berlin"



