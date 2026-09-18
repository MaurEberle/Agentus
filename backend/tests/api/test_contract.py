"""Lock implemented routers to python_backend_api.md. No guessed extra paths."""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from app.http.app import create_app
from app.http.contract import (
    NOT_FOUND_KEY,
    OWNER_BY_MODULE,
    PROVIDERS,
    ROUTES,
    SERVICE_STATUSES,
    STORE_IDS,
    route_key,
)
from app.http.routers import MODULES


def _live_owners() -> set[str]:
    owners: set[str] = set()
    for path in MODULES:
        try:
            importlib.import_module(path)
        except ImportError:
            continue
        owners.add(OWNER_BY_MODULE[path])
    return owners


def _app_api_keys() -> set[tuple[str, str]]:
    schema = create_app().openapi()
    keys: set[tuple[str, str]] = set()
    for path, ops in schema.get("paths", {}).items():
        if not str(path).startswith("/api"):
            continue
        for method in ops:
            if method.upper() in {"HEAD", "OPTIONS", "TRACE"}:
                continue
            if not isinstance(ops[method], dict):
                continue
            keys.add(route_key(method, str(path)))
    return keys


def test_contract_has_no_duplicate_keys() -> None:
    keys = [route_key(r.method, r.path) for r in ROUTES]
    assert len(keys) == len(set(keys))


def test_include_modules_are_in_contract_owners() -> None:
    assert set(MODULES) == set(OWNER_BY_MODULE)


def test_live_routes_match_contract_subset() -> None:
    live = _live_owners()
    expected = {route_key(r.method, r.path) for r in ROUTES if r.owner in live}
    actual = _app_api_keys()
    assert actual == expected


def test_unimplemented_owners_are_absent() -> None:
    live = _live_owners()
    actual = _app_api_keys()
    for route in ROUTES:
        if route.owner in live:
            continue
        assert route_key(route.method, route.path) not in actual


def test_health_shape(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert set(body["stores"]) == STORE_IDS
    assert set(body["stores"].values()) <= {"ok", "missing", "error"}
    assert "Ok" not in body


def test_about_no_paths_or_secrets(client: TestClient) -> None:
    response = client.get("/api/about")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["apiVersion"], str) and body["apiVersion"]
    if "runtime" in body:
        assert set(body["runtime"]) == {"ok"}
        assert isinstance(body["runtime"]["ok"], bool)
    text = response.text
    assert "dataDir" not in text
    assert "sk-" not in text
    assert "lmstudio" not in text


def test_unknown_path_message_key(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["messageKey"] == NOT_FOUND_KEY
    assert "Traceback" not in response.text


def test_validation_is_400_not_422(client: TestClient) -> None:
    response = client.post("/api/credentials", json={})
    assert response.status_code == 400
    assert response.json()["messageKey"] == "http.validation"


def test_session_shape(client: TestClient) -> None:
    response = client.get("/api/session")
    assert response.status_code == 200
    body = response.json()
    assert "activeNetworkId" in body
    assert body["serviceStatus"] in SERVICE_STATUSES
    assert "lmstudio" not in response.text


def test_settings_camel_case_no_theme(client: TestClient) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert "ollamaBaseUrl" in body
    assert "ollama_base_url" not in body
    assert "theme" not in body
    assert "locale" not in body
    assert body["helpChat"]["provider"] in PROVIDERS | {""}


def test_credentials_list_never_has_secret(client: TestClient) -> None:
    secret = "sk-contract-secret-value"
    created = client.post(
        "/api/credentials",
        json={"name": "c", "kind": "token", "secret": secret},
    )
    assert created.status_code == 201
    assert "secret" not in created.json()
    assert secret not in created.text
    listed = client.get("/api/credentials")
    assert listed.status_code == 200
    assert "items" in listed.json()
    assert secret not in listed.text
    assert all("secret" not in item for item in listed.json()["items"])


def test_data_location_shape(client: TestClient) -> None:
    response = client.get("/api/data-location")
    assert response.status_code == 200
    body = response.json()
    assert "dataDir" in body
    assert "stores" in body
    assert "secret" not in response.text


def test_runtime_ping_always_200(client: TestClient) -> None:
    response = client.post("/api/runtime/ping")
    assert response.status_code == 200
    assert "ok" in response.json()


def test_runtime_models_items(client: TestClient) -> None:
    response = client.get("/api/runtime/models")
    assert response.status_code == 200
    assert "items" in response.json()
    assert isinstance(response.json()["items"], list)


def test_no_auth_required(client: TestClient) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.headers.get("www-authenticate") is None
