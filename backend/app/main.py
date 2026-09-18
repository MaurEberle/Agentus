"""Process entry: persistenz init, then Uvicorn on loopback."""

from __future__ import annotations

import os

import uvicorn

from app.http.app import create_app


def assert_loopback(host: str) -> None:
    allowed = {"127.0.0.1", "localhost", "::1"}
    if host not in allowed:
        raise SystemExit(f"refusing non-loopback bind: {host}")


def _port() -> int:
    raw = os.environ.get("AGENTUS_NETWORK_API_PORT", "8765")
    try:
        port = int(raw)
    except ValueError:
        raise SystemExit(f"invalid AGENTUS_NETWORK_API_PORT: {raw}") from None
    if not 1 <= port <= 65535:
        raise SystemExit(f"invalid AGENTUS_NETWORK_API_PORT: {raw}")
    return port


def main() -> None:
    host = os.environ.get("AGENTUS_NETWORK_API_HOST", "127.0.0.1")
    port = _port()
    assert_loopback(host)
    try:
        from app.db import init as db_init

        db_init()
    except ImportError:
        pass
    try:
        from app.mcp import register_hooks

        register_hooks()
    except ImportError:
        pass
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
