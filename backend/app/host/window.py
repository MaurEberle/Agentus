from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from app.db.bootstrap import WindowGeom, save_window
from app.db.paths import webview_storage_dir
from app.http.paths import static_dir
from app.host.bridge import ChromeHostApi, inject_chrome_host
from app.host.geometry import MIN_H, MIN_W, start_placement
from app.host.native_frame import (
    configure_webview,
    enable_frameless_resize,
    resolve_app_icon,
    set_window_icon,
)
from app.host.server import start_uvicorn, stop_uvicorn, wait_health
from app.host.single_instance import WINDOW_TITLE, acquire, release

log = logging.getLogger("agentus.host")

_save_lock = threading.Lock()
_last_save = 0.0


def _dev() -> bool:
    return os.environ.get("AGENTUS_NETWORK_DEV", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def spa_window_url(port: int) -> str:
    """Bust WebView2's HTML cache after an overlay (same origin, new query)."""
    stamp = "0"
    folder = static_dir()
    if folder is not None:
        index = folder / "index.html"
        try:
            stamp = str(int(index.stat().st_mtime))
        except OSError:
            pass
    return f"http://127.0.0.1:{port}/?v={stamp}"


def webview_start_kwargs(*, icon_path: str | None) -> dict[str, Any]:
    storage = webview_storage_dir()
    storage.mkdir(parents=True, exist_ok=True)
    return {
        "gui": "edgechromium",
        "debug": _dev(),
        "icon": icon_path,
        "private_mode": False,
        "storage_path": str(storage),
    }


def _save_geom(window: Any) -> None:
    global _last_save
    now = time.monotonic()
    with _save_lock:
        if now - _last_save < 0.3:
            return
        _last_save = now
    try:
        save_window(
            WindowGeom(
                x=int(getattr(window, "x", 0) or 0),
                y=int(getattr(window, "y", 0) or 0),
                w=int(getattr(window, "width", 0) or getattr(window, "w", 0) or 0),
                h=int(getattr(window, "height", 0) or getattr(window, "h", 0) or 0),
                maximized=bool(getattr(window, "maximized", False)),
            )
        )
    except Exception:
        log.debug("save_window failed", exc_info=True)


def on_closing(server: Any, port: int) -> bool:
    _ = (server, port)
    try:
        from app.run.controller import get_controller

        get_controller().stop()
    except Exception:
        pass
    return True


def run_host(host: str, port: int) -> None:
    if not acquire():
        return
    server = None
    try:
        import webview

        configure_webview(webview)
        server = start_uvicorn(host, port)
        wait_health("127.0.0.1", port)
        geom, maximized = start_placement()
        api = ChromeHostApi()
        icon_path = resolve_app_icon()
        win = webview.create_window(
            title=WINDOW_TITLE,
            url=spa_window_url(port),
            js_api=api,
            width=geom.w,
            height=geom.h,
            x=geom.x,
            y=geom.y,
            frameless=True,
            easy_drag=False,
            resizable=True,
            min_size=(MIN_W, MIN_H),
            shadow=True,
        )
        api._window = win

        def _shown() -> None:
            enable_frameless_resize(win)
            set_window_icon(win, icon_path)
            if maximized:
                win.maximize()

        def _closing() -> bool:
            return on_closing(server, port)

        def _moved() -> None:
            _save_geom(win)

        def _resized() -> None:
            _save_geom(win)

        def _loaded() -> None:
            inject_chrome_host(win)

        win.events.shown += _shown
        win.events.closing += _closing
        win.events.moved += _moved
        win.events.resized += _resized
        win.events.loaded += _loaded
        try:
            webview.start(**webview_start_kwargs(icon_path=icon_path))
        except Exception as exc:
            raise SystemExit("host.webview2.missing") from exc
    finally:
        release()
        if server is not None:
            stop_uvicorn(server)
