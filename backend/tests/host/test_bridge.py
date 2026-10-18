from __future__ import annotations

from app.host.bridge import ChromeHostApi, inject_chrome_host


class _SaveWindow:
    def __init__(self, result: object) -> None:
        self.result = result
        self.save_filename = ""
        self.file_types: tuple[str, ...] = ()

    def create_file_dialog(
        self,
        kind: object,
        directory: str = "",
        allow_multiple: bool = False,
        save_filename: str = "",
        file_types: tuple[str, ...] = (),
    ) -> object:
        del kind, directory, allow_multiple
        self.save_filename = save_filename
        self.file_types = tuple(file_types)
        return self.result


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


def test_save_file_dialog_writes_json(tmp_path) -> None:
    from webview.util import parse_file_type

    target = tmp_path / "netz.json"
    api = ChromeHostApi()
    win = _SaveWindow((str(target),))
    api._window = win
    saved = api.saveFile(r"..\netz.json", '{"name": "mini"}\n', "json")
    assert saved == str(target)
    assert target.read_text(encoding="utf-8") == '{"name": "mini"}\n'
    assert win.save_filename == "netz.json"
    assert parse_file_type(win.file_types[0])[1] == "*.json"


def test_save_file_cancel_writes_nothing(tmp_path) -> None:
    target = tmp_path / "netz.json"
    api = ChromeHostApi()
    api._window = _SaveWindow(None)
    assert api.saveFile("netz.json", "{}", "json") is None
    assert not target.exists()


def test_save_file_writes_zip_bytes(tmp_path) -> None:
    import base64

    target = tmp_path / "netze.zip"
    api = ChromeHostApi()
    api._window = _SaveWindow((str(target),))
    payload = base64.b64encode(b"PK\x03\x04").decode("ascii")
    saved = api.saveFile("netze.zip", payload, "zip")
    assert saved == str(target)
    assert target.read_bytes() == b"PK\x03\x04"


def test_request_attention_without_native() -> None:
    api = ChromeHostApi()
    api.requestAttention(True)
    api.requestAttention(False)


def test_inject_sets_chrome_host() -> None:
    win = FakeWindow()
    inject_chrome_host(win)
    joined = "\n".join(win.js)
    assert "chromeHost" in joined
    assert "agentus-chrome-ready" in joined


def test_open_external_allows_public_http(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    api = ChromeHostApi()
    assert api.openExternal("https://example.com/docs") is True
    assert opened == ["https://example.com/docs"]
    assert api.openExternal("file:///C:/secret.txt") is False
    assert api.openExternal("https://user:secret@example.com/docs") is False
    assert api.openExternal("javascript:alert(1)") is False
    assert opened == ["https://example.com/docs"]
