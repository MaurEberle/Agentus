"""SPA static files from frontend/dist. Never swallow /api/*."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.routing import APIRoute
from starlette.routing import Match
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.http.errors import AppError


class _SpaRoute(APIRoute):
    """Do not match /api so later API routes and FastAPI 404 still apply."""

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        path = scope.get("path", "")
        if path == "/api" or str(path).startswith("/api/"):
            return Match.NONE, {}
        return super().matches(scope)


def resolve_static_dir() -> Path | None:
    env = os.environ.get("AGENTUS_NETWORK_STATIC_DIR")
    if env:
        path = Path(env).expanduser()
    else:
        path = Path(__file__).resolve().parents[2].parent / "frontend" / "dist"
    try:
        path = path.resolve()
    except OSError:
        return None
    if (path / "index.html").is_file():
        return path
    return None


def mount_spa(app: FastAPI) -> None:
    directory = resolve_static_dir()
    if directory is None:
        return
    static = StaticFiles(directory=str(directory), html=True)

    async def spa(request: Request, full_path: str = "") -> object:
        if full_path == "api" or full_path.startswith("api/"):
            raise AppError("http.notFound", status_code=404)
        return await static.get_response(full_path, request.scope)

    router = APIRouter(route_class=_SpaRoute)
    router.add_api_route("/", spa, methods=["GET", "HEAD"], include_in_schema=False)
    router.add_api_route(
        "/{full_path:path}", spa, methods=["GET", "HEAD"], include_in_schema=False
    )
    app.include_router(router)
