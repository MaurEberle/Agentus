from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.runtime.transport import install_transport


def test_ping_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    install_transport(monkeypatch, handler)
    response = client.post("/api/runtime/ping")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_models_fail_empty_items(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    install_transport(monkeypatch, handler)
    response = client.get("/api/runtime/models")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_models_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"models": [{"name": "llama3.2:1b", "size": 42}]}
        )

    install_transport(monkeypatch, handler)
    response = client.get("/api/runtime/models")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["name"] == "llama3.2:1b"
    assert item["sizeBytes"] == 42


def test_test_llm_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "model": "llama3.2:1b",
                    "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                },
            )
        return httpx.Response(200, json={"models": []})

    install_transport(monkeypatch, handler)
    response = client.post(
        "/api/runtime/test-llm",
        json={"provider": "ollama", "model": "llama3.2:1b"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
