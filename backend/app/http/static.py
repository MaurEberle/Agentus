"""SPA static files from frontend/dist. Never swallow /api/*."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.http.errors import AppError
from app.http.paths import static_dir


class _SpaRoute(APIRoute):
    """Do not match /api so later API routes and FastAPI 404 still apply."""

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        path = scope.get("path", "")
        if path == "/api" or str(path).startswith("/api/"):
            return Match.NONE, {}
        return super().matches(scope)


def resolve_static_dir() -> Path | None:
    return static_dir()


def is_client_route(full_path: str) -> bool:
    """A path the React router owns: no file extension in its last segment.

    ``/history/abc`` reloads the app; ``/assets/app-1234.js`` that is missing
    stays a 404 so a stale bundle is not answered with HTML.
    """
    last = full_path.rstrip("/").rsplit("/", 1)[-1]
    return "." not in last


def mount_spa(app: FastAPI) -> None:
    directory = resolve_static_dir()
    if directory is None:
        return
    static = StaticFiles(directory=str(directory), html=True)

    async def spa(request: Request, full_path: str = "") -> object:
        if full_path == "api" or full_path.startswith("api/"):
            raise AppError("http.notFound", status_code=404)
        try:
            response = await static.get_response(full_path, request.scope)
        except StarletteHTTPException as exc:
            # N7: reloading /history/... in a browser (NO_HOST or dev) gave a JSON 404.
            if exc.status_code != 404 or not is_client_route(full_path):
                raise
            response = await static.get_response("index.html", request.scope)
        if "text/html" in (response.headers.get("content-type") or ""):
            response.headers["Cache-Control"] = "no-store"
        return response

    router = APIRouter(route_class=_SpaRoute)
    router.add_api_route("/", spa, methods=["GET", "HEAD"], include_in_schema=False)
    router.add_api_route(
        "/{full_path:path}", spa, methods=["GET", "HEAD"], include_in_schema=False
    )
    app.include_router(router)
