from __future__ import annotations

from app.host.navigation import (
    guard_navigation,
    is_allowed_url,
    reset_navigation_guard,
)


def test_loopback_ok() -> None:
    assert is_allowed_url("http://127.0.0.1:8765/", 8765) is True
    assert is_allowed_url("http://localhost:8765/dashboard", 8765) is True
    assert is_allowed_url("http://[::1]:8765/", 8765) is True
    assert is_allowed_url("https://127.0.0.1:8765/", 8765) is True
    assert is_allowed_url("about:blank", 8765) is True
    assert is_allowed_url("about:blank/", 8765) is True


def test_rejects_foreign_and_file() -> None:
    assert is_allowed_url("https://evil.test/", 8765) is False
    assert is_allowed_url("file:///C:/x", 8765) is False
    assert is_allowed_url("http://127.0.0.1:9999/", 8765) is False
    assert is_allowed_url("http://127.0.0.1/", 8765) is False
    assert is_allowed_url("https://localhost/", 8765) is False
    assert is_allowed_url("https://127.0.0.1:443/", 8765) is False


class _Event:
    def __init__(self) -> None:
        self.handlers: list = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class _Control:
    def __init__(self) -> None:
        self.NavigationStarting = _Event()


class _Args:
    def __init__(self, uri: str) -> None:
        self.Uri = uri
        self.Cancel = False


class _SetterArgs:
    def __init__(self, uri: str) -> None:
        self._uri = uri
        self.cancelled = False

    def get_Uri(self) -> str:
        return self._uri

    def set_Cancel(self, value: bool) -> None:
        self.cancelled = value


def test_guard_cancels_foreign_navigation() -> None:
    reset_navigation_guard()
    control = _Control()

    class _Native:
        webview = control

    class _Window:
        native = _Native()

    assert guard_navigation(_Window(), 8765) is True
    assert guard_navigation(_Window(), 8765) is True
    assert len(control.NavigationStarting.handlers) == 1
    handler = control.NavigationStarting.handlers[0]

    blocked = _Args("https://evil.test/phish")
    handler(None, blocked)
    assert blocked.Cancel is True

    allowed = _Args("http://127.0.0.1:8765/app")
    handler(None, allowed)
    assert allowed.Cancel is False

    implicit = _Args("http://127.0.0.1/")
    handler(None, implicit)
    assert implicit.Cancel is True

    via_getter = _SetterArgs("file:///C:/secret")
    handler(None, via_getter)
    assert via_getter.cancelled is True
    reset_navigation_guard()


def test_guard_uses_browser_webview() -> None:
    reset_navigation_guard()
    control = _Control()

    class _Browser:
        webview = control

    class _Native:
        webview = None
        browser = _Browser()

    class _Window:
        native = _Native()

    assert guard_navigation(_Window(), 8765) is True
    assert len(control.NavigationStarting.handlers) == 1
    reset_navigation_guard()


def test_guard_without_control() -> None:
    reset_navigation_guard()

    class _Window:
        native = None

    assert guard_navigation(_Window(), 8765) is False
