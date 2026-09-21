from __future__ import annotations

from pathlib import Path

import pytest

from app.runtime.models import PingResult
from app.runtime.ollama_daemon import (
    ensure_local_ollama,
    is_loopback_base,
    ollama_launch_argv,
    reset_for_tests,
    start_local_ollama_background,
)


@pytest.fixture(autouse=True)
def _reset_daemon() -> None:
    reset_for_tests()
    yield
    reset_for_tests()


def test_loopback_hosts() -> None:
    assert is_loopback_base(None) is True
    assert is_loopback_base("http://127.0.0.1:11434") is True
    assert is_loopback_base("http://localhost:11434") is True
    assert is_loopback_base("http://192.168.1.9:11434") is False
    assert is_loopback_base("https://ollama.example") is False


def test_launch_prefers_app_exe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.install_detect.shutil.which", lambda name: None)
    app = tmp_path / "Programs" / "Ollama" / "ollama app.exe"
    exe = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    app.parent.mkdir(parents=True)
    app.write_bytes(b"MZ")
    exe.write_bytes(b"MZ")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    argv = ollama_launch_argv()
    assert argv is not None
    assert argv[0] == str(app)
    assert argv[1:] == ["--hide", "--fast-startup"]


def test_launch_falls_back_to_serve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.install_detect.shutil.which", lambda name: None)
    exe = tmp_path / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    argv = ollama_launch_argv()
    assert argv == [str(exe), "serve"]


def test_ensure_skips_when_already_up(monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        "app.runtime.ollama_daemon.ping_ollama",
        lambda **kwargs: PingResult(ok=True),
    )
    monkeypatch.setattr("app.runtime.ollama_daemon._spawn_detached", spawned.append)
    monkeypatch.setattr(
        "app.runtime.ollama_daemon.ollama_launch_argv",
        lambda: [r"C:\missing\ollama.exe", "serve"],
    )
    assert ensure_local_ollama() is True
    assert spawned == []


def test_ensure_does_not_spawn_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        "app.runtime.ollama_daemon.ping_ollama",
        lambda **kwargs: PingResult(ok=False, message_key="runtime.unreachable"),
    )
    monkeypatch.setattr("app.runtime.ollama_daemon._spawn_detached", spawned.append)
    assert ensure_local_ollama(base_url="http://192.168.10.2:11434") is False
    assert spawned == []


def test_ensure_spawns_once_when_down(monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        "app.runtime.ollama_daemon.ping_ollama",
        lambda **kwargs: PingResult(ok=False, message_key="runtime.unreachable"),
    )
    monkeypatch.setattr("app.runtime.ollama_daemon._spawn_detached", spawned.append)
    cmd = [r"C:\Ollama\ollama app.exe", "--hide", "--fast-startup"]
    monkeypatch.setattr("app.runtime.ollama_daemon.ollama_launch_argv", lambda: cmd)
    assert ensure_local_ollama(wait_sec=0) is False
    assert ensure_local_ollama(wait_sec=0) is False
    assert spawned == [cmd]


def test_background_start_skipped_in_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        "app.runtime.ollama_daemon.ensure_local_ollama",
        lambda **kwargs: called.append("ensure"),
    )
    start_local_ollama_background()
    assert called == []
