"""Close Agentus and open it again (desktop window only).

The new process starts first and waits until this one has exited; only then
does it take the single-instance lock and the API port. This process closes
its window, cleans up and exits hard, so a hanging thread cannot block the
new instance.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from typing import Any

log = logging.getLogger("agentus.host.restart")

WAIT_PID_ENV = "AGENTUS_NETWORK_WAIT_PID"
WAIT_SEC = 90.0

_CREATE_NEW_PROCESS_GROUP = 0x00000200
_DETACHED_PROCESS = 0x00000008
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_SYNCHRONIZE = 0x00100000

_lock = threading.Lock()
_window: Any = None
_pending = False


def set_window(window: Any) -> None:
    global _window
    with _lock:
        _window = window


def can_restart() -> bool:
    with _lock:
        return _window is not None


def pending() -> bool:
    with _lock:
        return _pending


def reset_for_tests() -> None:
    global _window, _pending
    with _lock:
        _window = None
        _pending = False


def relaunch_argv() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *sys.argv[1:]]
    return [sys.executable, "-m", "app.main", *sys.argv[1:]]


def relaunch_env(pid: int) -> dict[str, str]:
    env = dict(os.environ)
    env[WAIT_PID_ENV] = str(pid)
    # PyInstaller: a new instance must set up its own environment, not inherit
    # the bootloader state of this one.
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    for key in list(env):
        if key == "_MEIPASS2" or key.startswith("_PYI_"):
            env.pop(key, None)
    return env


def _spawn(argv: list[str], env: dict[str, str]) -> None:
    kwargs: dict[str, Any] = {
        "args": argv,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": env,
        "cwd": os.getcwd(),
        "close_fds": True,
    }
    if sys.platform == "win32":
        flags = _CREATE_NEW_PROCESS_GROUP | _DETACHED_PROCESS
        kwargs["creationflags"] = flags | _CREATE_BREAKAWAY_FROM_JOB
        try:
            subprocess.Popen(**kwargs)
            return
        except OSError:
            kwargs["creationflags"] = flags
    subprocess.Popen(**kwargs)


def request_restart(*, delay_sec: float = 0.8) -> bool:
    """Start the next instance and close the window. False without a window."""
    global _pending
    with _lock:
        window = _window
        if window is None:
            return False
        if _pending:
            return True
        _pending = True
    try:
        _spawn(relaunch_argv(), relaunch_env(os.getpid()))
    except OSError:
        log.exception("could not start the new Agentus instance")
        with _lock:
            _pending = False
        return False
    log.info("restarting Agentus")
    # The HTTP answer goes out before the window closes.
    timer = threading.Timer(delay_sec, _close, args=(window,))
    timer.daemon = True
    timer.start()
    return True


def _close(window: Any) -> None:
    try:
        window.destroy()
    except Exception:
        log.exception("closing the window for a restart failed")
        exit_now()


def exit_now() -> None:
    """End this process at once. Used after the window closed for a restart."""
    try:
        logging.shutdown()
    finally:
        os._exit(0)


def wait_for_previous(*, timeout_sec: float = WAIT_SEC) -> None:
    """Block until the instance that started this one has exited."""
    raw = os.environ.pop(WAIT_PID_ENV, "").strip()
    if not raw:
        return
    try:
        pid = int(raw)
    except ValueError:
        return
    if pid <= 0 or pid == os.getpid():
        return
    if sys.platform != "win32":
        return
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.OpenProcess(_SYNCHRONIZE, False, pid)
    if not handle:
        return  # already gone
    try:
        kernel32.WaitForSingleObject(handle, int(timeout_sec * 1000))
    finally:
        kernel32.CloseHandle(handle)
