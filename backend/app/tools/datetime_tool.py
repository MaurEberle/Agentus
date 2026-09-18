from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.tools.models import ExecuteResult


def _zone(name: str):
    if name.upper() == "UTC" or name in {"Etc/UTC", "GMT"}:
        return timezone.utc
    return ZoneInfo(name)


def run(config: dict[str, Any] | None, args: dict[str, Any] | None) -> ExecuteResult:
    name = "UTC"
    if args and args.get("timezone"):
        name = str(args["timezone"]).strip() or "UTC"
    try:
        zone = _zone(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ExecuteResult(ok=False, error_key="tools.datetime.invalidTimezone")
    now = datetime.now(zone)
    return ExecuteResult(
        ok=True,
        result={
            "iso": now.isoformat(),
            "timezone": name,
            "unix": int(now.timestamp()),
        },
    )
