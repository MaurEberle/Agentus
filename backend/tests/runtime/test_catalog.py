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


def test_list_openai_models_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.openai.com/v1/models"
        assert request.headers.get("authorization") == "Bearer sk-openai"
        return httpx.Response(200, json={"data": [{"id": "gpt-4.1"}, {"id": "gpt-4o-mini"}]})

    install_transport(monkeypatch, handler)
    items = list_openai_compat_models("openai", secret="sk-openai")
    assert [item.name for item in items] == ["gpt-4.1", "gpt-4o-mini"]


def test_list_anthropic_models_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.anthropic.com/v1/models"
        assert request.headers.get("authorization") == "Bearer sk-ant"
        assert request.headers.get("x-api-key") == "sk-ant"
        assert request.headers.get("anthropic-version") == "2023-06-01"
        return httpx.Response(
            200,
            json={"data": [{"id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4"}]},
        )

    install_transport(monkeypatch, handler)
    items = list_openai_compat_models("anthropic", secret="sk-ant")
    assert items[0].name == "claude-sonnet-4-20250514"


def test_list_gemini_strips_models_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith("https://generativelanguage.googleapis.com/v1beta/openai/models")
        return httpx.Response(
            200,
            json={"data": [{"id": "models/gemini-2.0-flash"}, {"id": "gemini-2.5-pro"}]},
        )

    install_transport(monkeypatch, handler)
    items = list_openai_compat_models("gemini", secret="gem-key")
    assert [item.name for item in items] == ["gemini-2.0-flash", "gemini-2.5-pro"]


def test_list_xai_unauthorized(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    install_transport(monkeypatch, handler)
    with pytest.raises(RuntimeApiError) as err:
        list_openai_compat_models("xai", secret="nope")
    assert err.value.error_key == "runtime.unauthorized"