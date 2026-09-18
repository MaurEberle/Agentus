from __future__ import annotations

from app.host.bridge import ChromeHostApi, inject_chrome_host


class FakeWindow:
    def __init__(self) -> None:
        self.minimized = False
        self.maximized = False
        self.destroyed = False
        self.js: list[str] = []
        self.dialog_result: object = None

    def minimize(self) -> None:
        self.minimized = True

    def maximize(self) -> None:
        self.maximized = True

    def restore(self) -> None:
        self.maximized = False

    def destroy(self) -> None:
        self.destroyed = True

    def create_file_dialog(self, _kind: object) -> object:
        return self.dialog_result

    def evaluate_js(self, script: str) -> None:
        self.js.append(script)


def test_minimize_flag() -> None:
    api = ChromeHostApi()
    win = FakeWindow()
    api._window = win
    api.minimize()
    assert win.minimized is True
    api.maximize()
    assert api.isMaximized() is True
    api.restore()
    assert api.isMaximized() is False
    api.close()
    assert win.destroyed is True


def test_pick_folder_cancel() -> None:
    api = ChromeHostApi()
    win = FakeWindow()
    win.dialog_result = None
    api._window = win
    assert api.pickFolder() is None


def test_inject_sets_chrome_host() -> None:
    win = FakeWindow()
    inject_chrome_host(win)
    assert any("chromeHost" in script for script in win.js)
