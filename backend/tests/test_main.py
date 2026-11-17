from __future__ import annotations

import sys

import pytest

from app.main import assert_loopback
from app.stdio import ensure_stdio, uvicorn_kwargs


def test_assert_loopback_exported_from_main() -> None:
    assert_loopback("127.0.0.1")
    with pytest.raises(SystemExit, match="refusing non-loopback bind"):
        assert_loopback("0.0.0.0")


def test_ensure_stdio_when_stdout_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ensure_stdio()
    assert sys.stdout is not None
    assert sys.stderr is not None
    sys.stdout.isatty()
    sys.stderr.isatty()


def test_uvicorn_config_survives_noconsole_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn
    from fastapi import FastAPI

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ensure_stdio()
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    kwargs = uvicorn_kwargs()
    assert kwargs.get("use_colors") is False
    assert kwargs.get("lifespan") == "off"
    uvicorn.Config(FastAPI(), host="127.0.0.1", port=0, **kwargs)


def test_port_in_use_stops_before_bootstrap() -> None:
    import socket

    from app.main import _assert_port_free

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        port = holder.getsockname()[1]
        with pytest.raises(SystemExit, match="already in use"):
            _assert_port_free("127.0.0.1", port)


def test_free_port_passes() -> None:
    import socket

    from app.main import _assert_port_free

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    _assert_port_free("127.0.0.1", port)


def test_bootstrap_does_not_swallow_a_broken_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """N8: a broken app.db import started the app without persistence."""
    import app.db
    from app.main import _bootstrap

    def _broken() -> None:
        raise ImportError("broken module")

    monkeypatch.setattr(app.db, "init", _broken)
    with pytest.raises(ImportError, match="broken module"):
        _bootstrap()


def test_router_import_errors_stop_the_app(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import FastAPI

    from app.http import routers

    monkeypatch.setattr(routers, "MODULES", [*routers.MODULES, "app.http.routers.does_not_exist"])
    with pytest.raises(ModuleNotFoundError):
        routers.include_all(FastAPI())
