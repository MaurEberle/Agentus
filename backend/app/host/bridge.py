from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

_MAX_SAVE_CHARS = 32_000_000
_SAVE_FILTERS = {
    "json": "JSON (*.json)",
    "zip": "ZIP (*.zip)",
}


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

    def saveFile(self, name: str, content: str, kind: str = "json") -> str | None:
        """Show the system save dialog and write the export the user confirmed."""
        if self._window is None or not isinstance(content, str):
            return None
        if len(content) > _MAX_SAVE_CHARS:
            return None
        file_kind = str(kind or "").strip().lower()
        file_filter = _SAVE_FILTERS.get(file_kind)
        if file_filter is None:
            return None
        try:
            import webview

            chosen = self._window.create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename=_save_name(name, file_kind),
                file_types=(file_filter,),
            )
        except Exception:
            return None
        target = _first_path(chosen)
        if target is None:
            return None
        path = Path(target)
        try:
            if file_kind == "json":
                path.write_bytes(content.encode("utf-8"))
            else:
                path.write_bytes(base64.b64decode(content, validate=True))
        except (OSError, ValueError) as exc:
            raise RuntimeError("save failed") from exc
        return str(path)


def _save_name(name: str, kind: str) -> str:
    base = Path(str(name or "").replace("\x00", "")).name
    suffix = f".{kind}"
    if not base or base in {".", ".."}:
        base = "network.json" if kind == "json" else "networks.zip"
    if not base.lower().endswith(suffix):
        base = f"{base}{suffix}"
    return base[:180]


def _first_path(chosen: object) -> str | None:
    if not chosen:
        return None
    first = chosen[0] if isinstance(chosen, (list, tuple)) else chosen
    if not isinstance(first, str) or not first.strip():
        return None
    return first


def inject_chrome_host(window: Any) -> None:
    try:
        window.evaluate_js(
            "window.chromeHost = window.pywebview.api;"
            "window.dispatchEvent(new CustomEvent('agentus-chrome-ready'));"
        )
        window.evaluate_js("window.open = function(){ return null; };")
    except Exception:
        pass
