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
    response = TestClient(_with_dummy(), base_url="http://127.0.0.1").get("/api/_test/conflict")
    assert response.status_code == 409
    assert response.json() == {
        "messageKey": "credentials.inUse",
        "message": "helpChat.llm",
    }


def test_validation_is_400(api_env) -> None:
    response = TestClient(_with_dummy(), base_url="http://127.0.0.1").post("/api/_test/validate", json={})
    assert response.status_code == 400
    body = response.json()
    assert body["messageKey"] == "http.validation"
    assert "message" in body


def test_unhandled_is_500_without_traceback(api_env) -> None:
    client = TestClient(_with_dummy(), base_url="http://127.0.0.1", raise_server_exceptions=False)
    response = client.get("/api/_test/boom")
    assert response.status_code == 500
    body = response.json()
    assert body == {"messageKey": "http.internal"}
    assert "Traceback" not in response.text
    assert "sk-fixture-secret" not in response.text


def test_persist_errors_map_status(api_env) -> None:
    client = TestClient(_with_dummy(), base_url="http://127.0.0.1")
    invalid = client.get("/api/_test/persist-dir")
    assert invalid.status_code == 400
    assert invalid.json()["messageKey"] == "dataDir.invalidPath"
    missing = client.get("/api/_test/persist-missing")
    assert missing.status_code == 404
    assert missing.json()["messageKey"] == "db.notFound"


def _with_upstream_failures() -> FastAPI:
    import httpx

    from app.runtime.errors import RuntimeApiError

    app = create_app()

    @app.get("/api/_test/model-validate")
    def model_validate() -> None:
        _Item.model_validate({"x": "not-a-number"})

    @app.get("/api/_test/runtime")
    def runtime() -> None:
        raise RuntimeApiError("runtime.unreachable", detail="connect refused")

    @app.get("/api/_test/connect")
    def connect() -> None:
        raise httpx.ConnectError("refused")

    @app.get("/api/_test/read-timeout")
    def read_timeout() -> None:
        raise httpx.ReadTimeout("slow")

    @app.get("/api/_test/bad-url")
    def bad_url() -> None:
        raise httpx.InvalidURL("no scheme")

    return app


def test_service_validation_is_400(api_env) -> None:
    response = TestClient(_with_upstream_failures(), base_url="http://127.0.0.1").get("/api/_test/model-validate")
    assert response.status_code == 400
    assert response.json()["messageKey"] == "http.validation"
    assert response.json()["message"].startswith("x:")


def test_runtime_and_transport_errors_are_mapped(api_env) -> None:
    client = TestClient(_with_upstream_failures(), base_url="http://127.0.0.1")
    runtime = client.get("/api/_test/runtime")
    assert runtime.status_code == 502
    assert runtime.json() == {"messageKey": "runtime.unreachable", "message": "connect refused"}
    connect = client.get("/api/_test/connect")
    assert connect.status_code == 502
    assert connect.json() == {"messageKey": "runtime.unreachable"}
    timeout = client.get("/api/_test/read-timeout")
    assert timeout.status_code == 504
    assert timeout.json() == {"messageKey": "runtime.timeout"}
    bad = client.get("/api/_test/bad-url")
    assert bad.status_code == 400
    assert bad.json() == {"messageKey": "runtime.invalidUrl"}
