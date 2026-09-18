"""stdio for a Windows GUI-subsystem freeze (sys.stdout is None)."""

from __future__ import annotations

import os
import sys


def ensure_stdio() -> None:
    """Uvicorn DefaultFormatter calls sys.stdout.isatty(); noconsole leaves stdout None.

    Use a real ``nul`` file object (valid fileno). ColourizedFormatter is avoided
    via ``uvicorn_kwargs()`` so a True isatty() on Windows nul is harmless.
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
        sys.__stdout__ = sys.stdout
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")
        sys.__stderr__ = sys.stderr
    if sys.stdin is None:
        sys.stdin = open(os.devnull, "r", encoding="utf-8", errors="replace")
        sys.__stdin__ = sys.stdin


def _noconsole_log_config() -> dict[str, object]:
    from copy import deepcopy

    from uvicorn.config import LOGGING_CONFIG

    cfg = deepcopy(LOGGING_CONFIG)
    cfg["formatters"]["default"]["use_colors"] = False
    cfg["formatters"]["access"]["use_colors"] = False
    return cfg


def uvicorn_kwargs() -> dict[str, object]:
    """Avoid Uvicorn ColourizedFormatter (isatty) and lifespan stalls when frozen."""
    ensure_stdio()
    frozen = bool(getattr(sys, "frozen", False))
    tty = False
    try:
        tty = bool(sys.stdout.isatty())
    except Exception:
        tty = False
    if frozen or not tty:
        return {
            "use_colors": False,
            "log_config": _noconsole_log_config(),
            "access_log": False,
            "log_level": "warning",
            "loop": "asyncio",
            "http": "h11",
            "ws": "none",
            "lifespan": "off",
        }
    return {"use_colors": True}
