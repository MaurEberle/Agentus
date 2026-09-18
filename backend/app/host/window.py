from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from app.db.bootstrap import WindowGeom, load_bootstrap, save_window
from app.host.bridge import ChromeHostApi, inject_chrome_host
from app.host.geometry import MIN_H, MIN_W, from_bootstrap
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
    try:
        from app.common.http import client

        with client(timeout_sec=8.0) as http:
            http.post(f"http://127.0.0.1:{port}/api/run/stop")
    except Exception:
        pass
    return True


def run_host(host: str, port: int) -> None:
    if not acquire():
        return
    server = None
    try:
        import webview

        server = start_uvicorn(host, port)
        wait_health("127.0.0.1", port)
        bootstrap = load_bootstrap()
        geom = from_bootstrap(bootstrap.window)
        maximized = bool(bootstrap.window.maximized)
        api = ChromeHostApi()
        win = webview.create_window(
            title=WINDOW_TITLE,
            url=f"http://127.0.0.1:{port}/",
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
            webview.start(gui="edgechromium", debug=_dev())
        except Exception as exc:
            raise SystemExit("host.webview2.missing") from exc
    finally:
        release()
        if server is not None:
            stop_uvicorn(server)
