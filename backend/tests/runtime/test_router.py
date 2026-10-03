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


def test_resources_host_snapshot(client: TestClient) -> None:
    response = client.get("/api/runtime/resources")
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "host"
    assert "cpuPercent" in body
    assert "ramUsedBytes" in body
    assert "ramTotalBytes" in body
    assert body["ramTotalBytes"] >= 0
    assert isinstance(body.get("gpus"), list) or body.get("gpus") is None


def test_xai_models_need_credential(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call HTTP")

    install_transport(monkeypatch, handler)
    response = client.get("/api/runtime/models", params={"provider": "xai"})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["messageKey"] == "runtime.missingCredential"


def test_xai_models_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    created = client.post(
        "/api/credentials",
        json={"name": "xAI", "kind": "xai", "secret": "sk-xai-live"},
    )
    assert created.status_code == 201
    cred_id = created.json()["id"]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Bearer sk-xai-live"
        return httpx.Response(
            200, json={"data": [{"id": "grok-4"}, {"id": "grok-3-mini"}]}
        )

    install_transport(monkeypatch, handler)
    response = client.get(
        "/api/runtime/models",
        params={"provider": "xai", "credentialId": cred_id},
    )
    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == ["grok-3-mini", "grok-4"]
    assert "messageKey" not in response.json()
    assert "sk-xai-live" not in response.text


def test_test_llm_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/chat") or request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "model": "llama3.2:1b",
                    "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                },
            )
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, json={"model_info": {"llama.block_count": 16}})
        return httpx.Response(200, json={"models": []})

    install_transport(monkeypatch, handler)
    response = client.post(
        "/api/runtime/test-llm",
        json={"provider": "ollama", "model": "llama3.2:1b"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_model_stats_ollama(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.http.routers.runtime.get_model_stats",
        lambda provider, model, credential_id=None, base_url=None: (2048, 32768, []),
    )
    monkeypatch.setattr("app.http.routers.runtime.model_block_count", lambda *a, **k: 16)
    response = client.get("/api/runtime/model-stats", params={"provider": "ollama", "model": "llama3.2:1b"})
    assert response.status_code == 200
    body = response.json()
    assert body["contextMin"] == 2048
    assert body["contextMax"] == 32768
    assert body.get("steps") in ([], None)
    assert body["gpuLayers"] == 16


def test_model_stats_cloud_prefix(client: TestClient) -> None:
    response = client.get(
        "/api/runtime/model-stats",
        params={"provider": "xai", "model": "grok-4.5"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contextMax"] == 500000
    assert 500000 in body["steps"]
    assert "gpuLayers" not in body
