from __future__ import annotations

import os
import threading

import pytest

from app.host import restart


@pytest.fixture(autouse=True)
def _reset():
    restart.reset_for_tests()
    yield
    restart.reset_for_tests()


class FakeWindow:
    def __init__(self) -> None:
        self.closed = threading.Event()

    def destroy(self) -> None:
        self.closed.set()


def test_no_window_means_no_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(restart, "_spawn", lambda argv, env: pytest.fail("nothing to restart"))
    assert restart.can_restart() is False
    assert restart.request_restart() is False
    assert restart.pending() is False


def test_restart_starts_the_next_instance_then_closes_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list[tuple[list[str], dict[str, str]]] = []
    monkeypatch.setattr(restart, "_spawn", lambda argv, env: spawned.append((argv, env)))
    window = FakeWindow()
    restart.set_window(window)
    assert restart.request_restart(delay_sec=0.0) is True
    assert window.closed.wait(2.0)
    assert restart.pending() is True
    argv, env = spawned[0]
    assert argv[0]
    assert env[restart.WAIT_PID_ENV] == str(os.getpid())
    # A second request while closing does not start a third instance.
    assert restart.request_restart(delay_sec=0.0) is True
    assert len(spawned) == 1


def test_a_failed_spawn_keeps_the_app_open(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(argv, env):
        raise OSError("denied")

    monkeypatch.setattr(restart, "_spawn", fail)
    window = FakeWindow()
    restart.set_window(window)
    assert restart.request_restart(delay_sec=0.0) is False
    assert restart.pending() is False
    assert not window.closed.wait(0.1)


def test_the_new_instance_gets_a_clean_pyinstaller_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("_MEIPASS2", "C:/temp/_MEI1")
    monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", "C:/app")
    env = restart.relaunch_env(1234)
    assert env[restart.WAIT_PID_ENV] == "1234"
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert "_MEIPASS2" not in env
    assert "_PYI_APPLICATION_HOME_DIR" not in env


def test_relaunch_runs_the_module_outside_a_frozen_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr("sys.frozen", raising=False)
    argv = restart.relaunch_argv()
    assert argv[1:3] == ["-m", "app.main"]


@pytest.mark.parametrize("raw", ["", "abc", "0", "-5"])
def test_waiting_ignores_missing_or_bad_pids(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv(restart.WAIT_PID_ENV, raw)
    restart.wait_for_previous(timeout_sec=5)
    assert restart.WAIT_PID_ENV not in os.environ


def test_waiting_for_an_exited_process_returns_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    import sys
    import time

    done = subprocess.run([sys.executable, "-c", "pass"], check=True)
    assert done.returncode == 0
    # Not this process and almost certainly gone; must not block for the timeout.
    monkeypatch.setenv(restart.WAIT_PID_ENV, "999999")
    started = time.monotonic()
    restart.wait_for_previous(timeout_sec=5)
    assert time.monotonic() - started < 2
