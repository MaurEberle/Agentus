"""Include API routers. Missing domain modules are skipped."""

from __future__ import annotations

import importlib

from fastapi import FastAPI

MODULES = [
    "app.http.routers.meta",
    "app.http.routers.settings",
    "app.http.routers.credentials",
    "app.http.routers.data_location",
    "app.http.routers.session",
    "app.http.routers.runtime",
    "app.http.routers.tools",
    "app.http.routers.mcp",
    "app.http.routers.networks",
    "app.http.routers.run",
    "app.http.routers.runs",
    "app.http.routers.help_chat",
]


def include_all(app: FastAPI) -> None:
    for path in MODULES:
        try:
            mod = importlib.import_module(path)
        except ImportError:
            continue
        app.include_router(mod.router, prefix="/api")
