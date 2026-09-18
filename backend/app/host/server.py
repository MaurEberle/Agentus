from __future__ import annotations

import threading
import time

import uvicorn

from app.common.http import client
from app.http.app import create_app
from app.stdio import ensure_stdio, uvicorn_kwargs


def start_uvicorn(host: str, port: int) -> uvicorn.Server:
    ensure_stdio()
    app = create_app()
    extra = uvicorn_kwargs()
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        **extra,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()
    return server


def wait_health(host: str, port: int, timeout_sec: float = 20.0) -> None:
    deadline = time.time() + timeout_sec
    url = f"http://{host}:{port}/api/health"
    last: Exception | None = None
    while time.time() < deadline:
        try:
            with client(timeout_sec=1.0) as http:
                response = http.get(url)
            if response.status_code == 200:
                return
        except Exception as exc:
            last = exc
        time.sleep(0.15)
    raise SystemExit(f"API health check failed on {url}: {last}")


def stop_uvicorn(server: uvicorn.Server) -> None:
    server.should_exit = True
