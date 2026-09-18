from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.db.errors import ConfigError, NotFound
from app.http.app import create_app
from app.http.errors import AppError


class _Item(BaseModel):
    x: int


def _with_dummy() -> FastAPI:
    app = create_app()

    @app.get("/api/_test/conflict")
    def conflict() -> None:
        raise AppError("credentials.inUse", status_code=409, message="helpChat.llm")

    @app.post("/api/_test/validate")
    def validate(item: _Item) -> _Item:
        return item

    @app.get("/api/_test/boom")
    def boom() -> None:
        raise RuntimeError("Traceback must not leak sk-fixture-secret")

    @app.get("/api/_test/persist-dir")
    def persist_dir() -> None:
        raise ConfigError("dataDir.invalidPath")

    @app.get("/api/_test/persist-missing")
    def persist_missing() -> None:
        raise NotFound("db.notFound", store_id="workspace")

    return app


def test_app_error_409(api_env) -> None:
    response = TestClient(_with_dummy()).get("/api/_test/conflict")
    assert response.status_code == 409
    assert response.json() == {
        "messageKey": "credentials.inUse",
        "message": "helpChat.llm",
    }


def test_validation_is_400(api_env) -> None:
    response = TestClient(_with_dummy()).post("/api/_test/validate", json={})
    assert response.status_code == 400
    body = response.json()
    assert body["messageKey"] == "http.validation"
    assert "message" in body


def test_unhandled_is_500_without_traceback(api_env) -> None:
    client = TestClient(_with_dummy(), raise_server_exceptions=False)
    response = client.get("/api/_test/boom")
    assert response.status_code == 500
    body = response.json()
    assert body == {"messageKey": "http.internal"}
    assert "Traceback" not in response.text
    assert "sk-fixture-secret" not in response.text


def test_persist_errors_map_status(api_env) -> None:
    client = TestClient(_with_dummy())
    invalid = client.get("/api/_test/persist-dir")
    assert invalid.status_code == 400
    assert invalid.json()["messageKey"] == "dataDir.invalidPath"
    missing = client.get("/api/_test/persist-missing")
    assert missing.status_code == 404
    assert missing.json()["messageKey"] == "db.notFound"
