"""Web search, Hub search and details of the architect (fix/netz-architekt/entwurf.md, 8; E-14)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.architect import session as sessions
from app.architect.loop import available_tools
from app.architect.tools import ToolContext, app_lookup, run_tool
from app.db import architect as store
from app.llm.hub import HubFilesResponse, HubHit, HubSearchResponse, QuantFile
from app.settings.models import AppSettingsPatch, CredentialCreate
from app.settings.service import create_credential, patch_settings


def _names() -> set[str]:
    return {tool.name for tool in available_tools()}


def _ctx(session_id: str) -> ToolContext:
    return ToolContext(session=store.get_session(session_id), cloud=True, lookup=app_lookup)


def _call(ctx: ToolContext, name: str, args: dict):
    return run_tool(available_tools(), ctx, name, json.dumps(args))


def test_research_tools_follow_the_settings(client) -> None:
    names = _names()
    assert {"search_models", "model_details"} <= names and "web_search" not in names
    patch_settings(AppSettingsPatch(architect={"webSearchEnabled": True, "webSearchProvider": "searxng"}))
    assert "web_search" not in _names()  # SearXNG without an address
    patch_settings(AppSettingsPatch(architect={"webSearchBaseUrl": "http://localhost:8888"}))
    assert "web_search" in _names()
    patch_settings(AppSettingsPatch(architect={"hubCallsPerSession": 0, "webSearchesPerSession": 0}))
    assert not {"web_search", "search_models", "model_details"} & _names()


def test_web_search_uses_its_own_settings_and_budget(client, monkeypatch) -> None:
    patch_settings(
        AppSettingsPatch(
            architect={
                "webSearchEnabled": True,
                "webSearchProvider": "searxng",
                "webSearchBaseUrl": "http://localhost:8888",
                "webSearchesPerSession": 2,
            }
        )
    )
    seen = []

    def fake(kind, *, config, args, secret):
        seen.append((kind, config, args))
        return SimpleNamespace(ok=True, result={"results": [{"title": "Ollama", "url": "https://ollama.com", "snippet": "Run models."}]}, error_key=None)

    monkeypatch.setattr("app.tools.execute.execute_first_party", fake)
    row = sessions.create("anthropic", "claude", None)
    ctx = _ctx(row.id)
    first = _call(ctx, "web_search", {"query": "ollama tool calling"})
    assert first.ok and first.params == {"query": "ollama tool calling", "count": 1}
    assert json.loads(first.content)["results"][0]["url"] == "https://ollama.com"
    assert seen[0][1]["searchProvider"] == "searxng" and seen[0][1]["searchBaseUrl"] == "http://localhost:8888"
    assert _call(ctx, "web_search", {"query": "zweite"}).ok
    third = _call(ctx, "web_search", {"query": "dritte"})
    assert not third.ok and third.key == "architect.tool.limit" and len(seen) == 2
    assert ctx.session.counters["webSearches"] == 2


def test_hub_search_and_details_share_a_budget_and_respect_the_lock(client, monkeypatch) -> None:
    patch_settings(AppSettingsPatch(architect={"hubCallsPerSession": 2}))
    monkeypatch.setattr("app.architect.research._gpus", lambda: [{"name": "RTX", "vramTotalGB": 16.0, "vramUsedGB": 1.0}])
    hits = [
        HubHit(id="org/small-GGUF", url="u", tools=True, parameters="8B", parameterCount=8_000_000_000, contextLength=32768),
        HubHit(id="org/big-GGUF", url="u", tools=True, parameters="32B", parameterCount=32_000_000_000),
    ]
    calls = []

    def fake_search(**kwargs):
        calls.append(kwargs)
        return HubSearchResponse(items=hits)

    monkeypatch.setattr("app.llm.hub.search_hub", fake_search)
    monkeypatch.setattr(
        "app.llm.hub.repo_files",
        lambda repo: HubFilesResponse(
            id=repo,
            url=f"https://huggingface.co/{repo}",
            license="apache-2.0",
            installable=True,
            quants=[QuantFile(quant="Q4_K_M", filename="m.gguf", sizeBytes=4_900_000_000, tag=f"hf.co/{repo}:Q4_K_M")],
        ),
    )
    row = sessions.create("ollama", "qwen3:14b", None)
    ctx = _ctx(row.id)

    monkeypatch.setattr("app.llm.hub.hub_cooldown", lambda: 42)
    locked = _call(ctx, "search_models", {"query": "coder"})
    assert not locked.ok and locked.params == {"seconds": 42} and not calls
    monkeypatch.setattr("app.llm.hub.hub_cooldown", lambda: 0)

    found = _call(ctx, "search_models", {"query": "coder", "size": "14"})
    rows = json.loads(found.content)["models"]
    assert found.ok and [item["gpuFit"] for item in rows] == ["fits", "tooBig"]
    assert rows[0]["q4GB"] == 4.8 and calls[0]["capabilities"] == "tools" and calls[0]["size"] == "14"
    details = _call(ctx, "model_details", {"repo": "org/small-GGUF"})
    quant = json.loads(details.content)["quants"][0]
    assert details.ok and quant == {"quant": "Q4_K_M", "sizeGB": 4.9, "ollamaTag": "hf.co/org/small-GGUF:Q4_K_M", "installed": False, "gpuFit": "fits"}
    over = _call(ctx, "model_details", {"repo": "org/big-GGUF"})
    assert not over.ok and over.key == "architect.tool.limit"


def test_credentials_of_the_architect_count_as_in_use(client) -> None:
    cred = create_credential(CredentialCreate(name="Brave", kind="brave", secret="brave-key-000000000"))
    patch_settings(AppSettingsPatch(architect={"webSearchCredentialId": cred.id}))
    listed = next(item for item in client.get("/api/credentials").json()["items"] if item["id"] == cred.id)
    assert listed["inUse"] is True
