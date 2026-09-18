from __future__ import annotations

_degraded: bool = False


def set_help_degraded(value: bool) -> None:
    global _degraded
    _degraded = bool(value)
    try:
        from app.help.status import set_degraded

        set_degraded(value)
    except ImportError:
        pass


def get_help_degraded() -> bool:
    return _degraded
