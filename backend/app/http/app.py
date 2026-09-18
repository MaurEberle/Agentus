"""FastAPI factory. Domain routers hang off include_all; host reuses create_app()."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from starlette.middleware.cors import CORSMiddleware

MODEL_CONFIG = ConfigDict(
    populate_by_name=True,
    alias_generator=to_camel,
    ser_json_by_alias=True,
)


class ApiModel(BaseModel):
    """Base for HTTP models. Routers subclass this; do not copy ConfigDict."""

    model_config = MODEL_CONFIG


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def api_version() -> str:
    env = os.environ.get("AGENTUS_NETWORK_API_VERSION", "").strip()
    if env:
        return env
    try:
        from importlib.metadata import version

        return version("agentus-network")
    except Exception:
        return "0.1.0"


def _is_loopback_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def cors_origins() -> list[str]:
    origins: list[str] = []
    if env_flag("AGENTUS_NETWORK_DEV"):
        origins.extend(["http://127.0.0.1:5173", "http://localhost:5173"])
    extra = os.environ.get("AGENTUS_NETWORK_CORS_ORIGINS", "")
    for part in extra.split(","):
        origin = part.strip()
        if origin and _is_loopback_origin(origin) and origin not in origins:
            origins.append(origin)
    return origins


def create_app() -> FastAPI:
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        ser_json_by_alias=True,
    )
    ApiModel.model_config = model_config

    dev = env_flag("AGENTUS_NETWORK_DEV")
    app = FastAPI(
        title="Agentus Network API",
        version=api_version(),
        docs_url="/docs" if dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if dev else None,
    )

    from app.http.errors import register_exception_handlers
    from app.http.routers import include_all
    from app.http.static import mount_spa

    register_exception_handlers(app)
    origins = cors_origins()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    include_all(app)
    mount_spa(app)
    return app
