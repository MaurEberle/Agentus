"""Suite-wide guards that keep the tests hermetic.

1. Every ``app`` module is imported once before any test runs. Routers bind
   helpers with ``from x import f`` on first import; when that first import
   happened inside a test that had ``f`` monkeypatched, later tests kept the
   fake. Importing up front makes those bindings point at the real code.
2. Connections to the Ollama port are refused at once. A forgotten mock then
   fails fast with a clear message instead of waiting on timeouts, and a
   developer's real Ollama never receives unloads or model calls from tests.
"""

from __future__ import annotations

import importlib
import pkgutil
import socket

import pytest

import app

OLLAMA_PORT = 11434


def _import_all() -> None:
    for info in pkgutil.walk_packages(app.__path__, "app."):
        importlib.import_module(info.name)


_import_all()


def _port(address: object) -> int | None:
    if isinstance(address, tuple) and len(address) >= 2:
        try:
            return int(address[1])
        except (TypeError, ValueError):
            return None
    return None


_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _guarded_connect(self: socket.socket, address: object) -> None:
    if _port(address) == OLLAMA_PORT:
        raise ConnectionRefusedError(f"tests must not reach Ollama on port {OLLAMA_PORT}; mock the call")
    return _real_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: object) -> int:
    if _port(address) == OLLAMA_PORT:
        return 10061  # WSAECONNREFUSED
    return _real_connect_ex(self, address)


@pytest.fixture(autouse=True, scope="session")
def _no_real_ollama():
    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _guarded_connect_ex  # type: ignore[method-assign]
    yield
    socket.socket.connect = _real_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _real_connect_ex  # type: ignore[method-assign]
