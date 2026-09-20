from __future__ import annotations

import httpx
import pytest

from app.runtime.catalog import list_openai_compat_models
from app.runtime.errors import RuntimeApiError
from tests.runtime.transport import install_transport


def test_list_xai_missing_secret_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call HTTP")

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as err:
        list_openai_compat_models("xai")
    assert err.value.error_key == "runtime.missingCredential"


def test_list_xai_models_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert str(request.url) == "https://api.x.ai/v1/models"
        assert request.headers.get("authorization") == "Bearer sk-xai-test"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "grok-3", "object": "model"},
                    {"id": "grok-4", "object": "model"},
                    {"id": "grok-3"},
                ]
            },
        )

    install_transport(monkeypatch, handler)
    items = list_openai_compat_models("xai", secret="sk-xai-test")
    assert [item.name for item in items] == ["grok-3", "grok-4"]
    assert len(seen) == 1


def test_list_xai_unauthorized(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as err:
        list_openai_compat_models("xai", secret="nope")
    assert err.value.error_key == "runtime.unauthorized"