"""Include API routers. Every router is required; an import error stops the app (N8)."""

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
    "app.http.routers.prompts",
    "app.http.routers.models",
    "app.http.routers.run",
    "app.http.routers.runs",
    "app.http.routers.help_chat",
]


def include_all(app: FastAPI) -> None:
    for path in MODULES:
        mod = importlib.import_module(path)
        app.include_router(mod.router, prefix="/api")
