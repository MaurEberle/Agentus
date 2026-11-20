"""App log file (B1): ``agentus.*`` and ``app.*`` loggers to ``logs/agentus.log``.

The desktop app sends stdout and stderr to ``nul``. Without this file, errors outside
a run (memory not stored, tool crashes, own Ollama, MCP) were lost. The file rotates
at 5 MB and keeps three old files. Messages are masked like run logs.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.db.paths import local_app_data

LOG_NAME = "agentus.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUPS = 3
LOGGER_NAMES = ("agentus", "app")
# Off in tests and for anyone who wants the console only.
DISABLE_ENV = "AGENTUS_NETWORK_NO_LOG_FILE"

_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s"
_installed: RotatingFileHandler | None = None
_previous_hook = None


def log_dir() -> Path:
    return local_app_data() / "logs"


def log_path() -> Path:
    return log_dir() / LOG_NAME


class _MaskedFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from app.common.secrets import mask_text

        return mask_text(super().format(record))


def setup_app_log(path: Path | None = None) -> Path | None:
    """Attach the rotating file handler once. Returns the file, or None when off or not writable."""
    global _installed
    if _installed is not None:
        return Path(_installed.baseFilename)
    if os.environ.get(DISABLE_ENV):
        return None
    target = path or log_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            target, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8", delay=True
        )
    except OSError:
        return None
    handler.setLevel(logging.INFO)
    handler.setFormatter(_MaskedFormatter(_FORMAT))
    for name in LOGGER_NAMES:
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        if logger.level == logging.NOTSET or logger.level > logging.INFO:
            logger.setLevel(logging.INFO)
    _install_thread_hook()
    _installed = handler
    logging.getLogger("agentus").info(
        "app start pid=%s frozen=%s", os.getpid(), bool(getattr(sys, "frozen", False))
    )
    return target


def remove_app_log() -> None:
    """Detach the handler and the thread hook (tests)."""
    global _installed, _previous_hook
    if _installed is None:
        return
    for name in LOGGER_NAMES:
        logging.getLogger(name).removeHandler(_installed)
    _installed.close()
    _installed = None
    if _previous_hook is not None:
        threading.excepthook = _previous_hook
        _previous_hook = None


def _install_thread_hook() -> None:
    """An exception that ends a worker thread went to stderr, that is nowhere."""
    global _previous_hook
    previous = threading.excepthook
    _previous_hook = previous

    def hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is not SystemExit:
            name = args.thread.name if args.thread is not None else "?"
            logging.getLogger("agentus.crash").error(
                "thread %s ended with an error",
                name,
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
        previous(args)

    threading.excepthook = hook


def open_log_dir() -> bool:
    """Open the log folder in the file manager (Windows). False elsewhere or when it fails."""
    folder = log_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    starter = getattr(os, "startfile", None)
    if starter is None:
        return False
    try:
        starter(str(folder))
    except OSError:
        return False
    return True
