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
