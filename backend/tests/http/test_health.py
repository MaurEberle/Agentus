from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.vault import put
from app.http.app import create_app


def test_health_ok_camel_case(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert "ok" in body
    assert "Ok" not in body
    assert body["ok"] is True
    assert body["stores"] == {
        "settings": "ok",
        "help": "ok",
        "workspace": "ok",
        "history": "ok",
    }


def test_health_without_db(api_env) -> None:
    response = TestClient(create_app()).get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "stores" not in body


def test_about_has_version_no_paths_or_secrets(client: TestClient) -> None:
    put("cred-1", "sk-fixture-secret-value")
    response = client.get("/api/about")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["apiVersion"], str)
    assert body["apiVersion"]
    text = response.text
    assert "dataDir" not in text
    assert "sk-fixture-secret-value" not in text
    assert "LOCALAPPDATA" not in text


def test_unknown_api_path_is_not_found(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["messageKey"] == "http.notFound"


def test_post_health_has_message_key(client: TestClient) -> None:
    response = client.post("/api/health")
    assert response.status_code in {404, 405}
    assert response.json().get("messageKey")


def test_loopback_uvicorn_health(api_env) -> None:
    import socket
    import threading
    import time

    import httpx
    import uvicorn

    from app.db import init

    init()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 8
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    try:
        response = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2.0)
    finally:
        server.should_exit = True
        thread.join(timeout=3)
    assert response.status_code == 200
    assert response.json()["ok"] is True
