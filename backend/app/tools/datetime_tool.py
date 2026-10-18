from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.tools.models import ExecuteResult

DATE_ACTION_ORDER = ("now", "add", "diff", "parts", "convert")
ACTIONS = frozenset(DATE_ACTION_ORDER)
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MAX_SHIFT = 1_000_000


def _fail(key: str) -> ExecuteResult:
    return ExecuteResult(ok=False, error_key=key)


def _zone(name: str):
    if name.upper() == "UTC" or name in {"Etc/UTC", "GMT"}:
        return timezone.utc
    return ZoneInfo(name)


def _stamp(moment: datetime, name: str) -> dict[str, object]:
    return {
        "iso": moment.isoformat(),
        "timezone": name,
        "unix": int(moment.timestamp()),
    }


def _parts(moment: datetime) -> dict[str, object]:
    return {
        "year": moment.year,
        "month": moment.month,
        "day": moment.day,
        "hour": moment.hour,
        "minute": moment.minute,
        "second": moment.second,
        "weekday": _WEEKDAYS[moment.weekday()],
        "weekdayIndex": moment.isoweekday(),
    }


def _int(args: dict[str, Any], key: str) -> int:
    value = args.get(key)
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        raise ValueError(key)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        value = int(value.strip())
    if not isinstance(value, int) or abs(value) > _MAX_SHIFT:
        raise ValueError(key)
    return value


def _moment(raw: object, zone) -> datetime:
    if raw is None or raw == "":
        return datetime.now(zone)
    if isinstance(raw, bool):
        raise ValueError("instant")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return datetime.fromtimestamp(int(raw), timezone.utc).astimezone(zone)
    text = str(raw).strip()
    if not text:
        return datetime.now(zone)
    if text.lstrip("-").isdigit():
        return datetime.fromtimestamp(int(text), timezone.utc).astimezone(zone)
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=zone)
    return moment.astimezone(zone)


def run(config: dict[str, Any] | None, args: dict[str, Any] | None) -> ExecuteResult:
    del config
    raw = args or {}
    action = str(raw.get("action") or "now").strip().lower() or "now"
    if action not in ACTIONS:
        return _fail("tools.datetime.invalidAction")
    name = str(raw.get("timezone") or "UTC").strip() or "UTC"
    try:
        zone = _zone(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return _fail("tools.datetime.invalidTimezone")
    try:
        if action == "now":
            result = _stamp(datetime.now(zone), name)
        elif action == "add":
            shifted = _moment(raw.get("at"), zone) + timedelta(
                days=_int(raw, "days"),
                hours=_int(raw, "hours"),
                minutes=_int(raw, "minutes"),
            )
            result = _stamp(shifted, name)
        elif action == "diff":
            if not str(raw.get("start") or "").strip() or not str(raw.get("end") or "").strip():
                raise ValueError("diff")
            start = _moment(raw.get("start"), zone)
            end = _moment(raw.get("end"), zone)
            seconds = int((end - start).total_seconds())
            result = {
                "seconds": seconds,
                "hours": seconds / 3600,
                "days": seconds / 86400,
                "start": _stamp(start, name),
                "end": _stamp(end, name),
            }
        elif action == "parts":
            moment = _moment(raw.get("at"), zone)
            result = {**_stamp(moment, name), **_parts(moment)}
        else:
            target_name = str(raw.get("toTimezone") or "").strip()
            if not target_name:
                raise ValueError("convert")
            target = _zone(target_name)
            shown = _moment(raw.get("at"), zone).astimezone(target)
            result = _stamp(shown, target_name)
    except ZoneInfoNotFoundError:
        return _fail("tools.datetime.invalidTimezone")
    except (ValueError, OverflowError, OSError):
        return _fail("tools.datetime.invalidInstant")
    return ExecuteResult(ok=True, result=result)
