"""Start a local Ollama daemon if it is installed but not listening.

Never stops Ollama. Only acts on loopback base URLs. Prefer the official
Windows ``ollama app.exe`` helper so GUI settings (model dir) apply;
fall back to ``ollama serve``.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from app.install_detect import ollama_app_exe_path, ollama_exe_path
from app.runtime.ollama import ping_ollama
from app.settings.defaults import DEFAULT_OLLAMA_BASE_URL

log = logging.getLogger("agentus.runtime.ollama")

_CREATE_NO_WINDOW = 0x08000000
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000

_spawned = False
_lock = threading.Lock()

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def reset_for_tests() -> None:
    global _spawned
    with _lock:
        _spawned = False


def is_loopback_base(url: str | None) -> bool:
    raw = (url or "").strip() or DEFAULT_OLLAMA_BASE_URL
    if "://" not in raw:
        raw = f"http://{raw}"
    host = (urlparse(raw).hostname or "").lower()
    return host in _LOOPBACK_HOSTS


def ollama_launch_argv() -> list[str] | None:
    app = ollama_app_exe_path()
    if app is not None:
        return [str(app), "--hide", "--fast-startup"]
    exe = ollama_exe_path()
    if exe is not None:
        return [str(exe), "serve"]
    return None


def _configured_base(override: str | None) -> str:
    if override and override.strip():
        return override.strip()
    try:
        from app.runtime.urls import ollama_native_root

        return ollama_native_root(None)
    except Exception:
        return DEFAULT_OLLAMA_BASE_URL


def _spawn_detached(cmd: list[str]) -> None:
    kwargs: dict = {
        "args": cmd,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": str(Path(cmd[0]).parent),
        "close_fds": True,
    }
    if sys.platform == "win32":
        flags = _CREATE_NEW_PROCESS_GROUP | _DETACHED_PROCESS | _CREATE_NO_WINDOW
        kwargs["creationflags"] = flags | _CREATE_BREAKAWAY_FROM_JOB
        try:
            subprocess.Popen(**kwargs)
            return
        except OSError:
            kwargs["creationflags"] = flags
    subprocess.Popen(**kwargs)


def ensure_local_ollama(*, base_url: str | None = None, wait_sec: float = 0.0) -> bool:
    """If the configured Ollama URL is loopback and down, start the local daemon.

    Returns whether a subsequent ping succeeded. Does not kill or restart an
    already running server. Spawns at most once per process.
    """
    global _spawned
    url = _configured_base(base_url)
    if not is_loopback_base(url):
        return ping_ollama(base_url=url, timeout_sec=1.5).ok
    if ping_ollama(base_url=url, timeout_sec=1.5).ok:
        return True
    cmd = ollama_launch_argv()
    if cmd is None:
        return False
    with _lock:
        if not _spawned:
            try:
                _spawn_detached(cmd)
                _spawned = True
            except OSError:
                log.debug("ollama spawn failed", exc_info=True)
                return False
    if wait_sec <= 0:
        return ping_ollama(base_url=url, timeout_sec=1.5).ok
    deadline = time.monotonic() + wait_sec
    while time.monotonic() < deadline:
        if ping_ollama(base_url=url, timeout_sec=1.0).ok:
            return True
        time.sleep(0.4)
    return False


def start_local_ollama_background(*, wait_sec: float = 20.0) -> None:
    """Fire-and-forget so the UI can open while Ollama comes up."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if os.environ.get("AGENTUS_NETWORK_NO_OLLAMA", "").strip().lower() in {"1", "true", "yes"}:
        return

    def _run() -> None:
        try:
            ensure_local_ollama(wait_sec=wait_sec)
        except Exception:
            log.debug("ensure_local_ollama failed", exc_info=True)

    threading.Thread(target=_run, name="ollama-daemon", daemon=True).start()
