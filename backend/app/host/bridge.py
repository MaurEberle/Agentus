from __future__ import annotations

from typing import Any


class ChromeHostApi:
    def __init__(self) -> None:
        self._window: Any = None

    def minimize(self) -> None:
        if self._window is not None:
            self._window.minimize()

    def maximize(self) -> None:
        if self._window is not None:
            self._window.maximize()

    def restore(self) -> None:
        if self._window is not None:
            self._window.restore()

    def close(self) -> None:
        if self._window is not None:
            self._window.destroy()

    def isMaximized(self) -> bool:
        if self._window is None:
            return False
        return bool(getattr(self._window, "maximized", False))

    def requestAttention(self, active: bool = True) -> None:
        from app.host.native_frame import flash_window

        flash_window(self._window, bool(active))

    def openExternal(self, url: str) -> bool:
        from app.host.navigation import open_external_url

        return open_external_url(url)

    def pickFolder(self) -> str | None:
        if self._window is None:
            return None
        try:
            import webview

            chosen = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        except Exception:
            return None
        if not chosen:
            return None
        first = chosen[0] if isinstance(chosen, (list, tuple)) else chosen
        return str(first) if first else None


def inject_chrome_host(window: Any) -> None:
    try:
        window.evaluate_js(
            "window.chromeHost = window.pywebview.api;"
            "window.dispatchEvent(new CustomEvent('agentus-chrome-ready'));"
        )
        window.evaluate_js("window.open = function(){ return null; };")
    except Exception:
        pass
