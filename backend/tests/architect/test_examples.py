"""The architect's example index (fix/netz-architekt/entwurf.md, 6 and 15)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.architect import examples
from app.architect import session as sessions
from app.architect.draft import compile_draft
from app.architect.loop import available_tools
from app.architect.tools import ToolContext, app_lookup, run_tool
from app.common.components import catalog_dir
from app.db import architect as store
from app.llm.catalog import InstalledModel, InstalledResponse
from app.settings.models import AppSettingsPatch
from app.settings.service import patch_settings

CHAIN = {
    "name": "Übersetzer-Kette",
    "description": "Fasst Texte zusammen und übersetzt sie ins Englische.",
    "tags": ["übersetzung"],
    "nodes": [
        {"ref": "chat", "type": "chat_input"},
        {"ref": "writer", "type": "agent", "data": {"displayName": "Übersetzer", "systemPrompt": "Geheimer Prompt: übersetze."}},
        {"ref": "model", "type": "llm", "data": {"provider": "ollama", "model": "qwen3:14b"}},
        {"ref": "end", "type": "end"},
    ],
    "links": [["chat", "writer"], ["model", "writer"], ["writer", "end"]],
}


@pytest.fixture
def shipped(tmp_path, monkeypatch) -> Path:
    folder = tmp_path / "examples"
    folder.mkdir()
    monkeypatch.setattr(examples, "examples_dir", lambda: folder)
    return folder


def _installed(monkeypatch) -> None:
    model = InstalledModel(name="qwen3:14b", parameter_size="14B", tools=True, context_length=65536)
    monkeypatch.setattr("app.llm.catalog.list_installed", lambda: InstalledResponse(items=[model]))


def _write(folder: Path, name: str, title: str, goal: str, draft: dict) -> None:
    payload = {"id": name, "title": title, "brief": {"goal": goal}, "draft": draft, "catalogHash": "alt"}
    (folder / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


def _search(query: str, *, cloud: bool = False, own: bool = False, embedder=None) -> dict:
    return examples.search(query, lookup=app_lookup(), own=own, cloud=cloud, send_paths=False, embedder=embedder)


def test_keywords_find_shipped_examples_and_follow_changes(client, shipped, monkeypatch) -> None:
    _installed(monkeypatch)
    research = copy.deepcopy(CHAIN)
    research["name"] = "Recherche"
    _write(shipped, "recherche", "Recherche mit Quellen", "Themen im Web recherchieren und mit Quellen berichten", research)
    _write(shipped, "kette", "Übersetzer-Kette", "Texte zusammenfassen und übersetzen", CHAIN)
    found = _search("Ich will Texte übersetzen lassen")
    assert found["method"] == "keywords" and found["count"] == 2
    assert [item["title"] for item in found["results"]][0] == "Übersetzer-Kette"
    assert found["results"][0]["outdated"] is True  # built for another catalog
    assert found["results"][0]["draft"]["nodes"][1]["data"]["systemPrompt"] == "Geheimer Prompt: übersetze."
    (shipped / "recherche.json").unlink()
    assert _search("Recherche Quellen")["count"] == 1


def test_own_networks_only_when_allowed_and_without_prompts_for_the_cloud(client, shipped, monkeypatch) -> None:
    _installed(monkeypatch)
    document = compile_draft(CHAIN, app_lookup()).document
    assert client.post("/api/networks", json=document).status_code == 201
    assert _search("übersetzen", own=False)["count"] == 0
    local = _search("übersetzen", own=True)
    assert local["results"][0]["source"] == "own"
    assert local["results"][0]["draft"]["nodes"][1]["data"]["systemPrompt"].startswith("Geheimer")
    cloud = _search("übersetzen", own=True, cloud=True)
    hit = cloud["results"][0]
    assert hit["promptsHidden"] is True and "systemPrompt" not in hit["draft"]["nodes"][1]["data"]
    assert hit["outdated"] is False


def test_invalid_own_networks_are_no_examples(client, shipped, monkeypatch) -> None:
    _installed(monkeypatch)
    broken = copy.deepcopy(CHAIN)
    broken["links"] = [["chat", "writer"], ["writer", "end"]]  # the agent has no LLM
    client.post("/api/networks", json=compile_draft(broken, app_lookup()).document)
    assert _search("übersetzen", own=True)["count"] == 0


class _FakeEmbedder:
    model = "fake-embed"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[1.0, 0.0] if "übersetz" in text.lower() else [0.0, 1.0] for text in texts]


def test_embeddings_rank_and_are_kept_until_the_content_changes(client, shipped, monkeypatch) -> None:
    _installed(monkeypatch)
    _write(shipped, "recherche", "Recherche", "Quellen sammeln", CHAIN | {"name": "Recherche"})
    _write(shipped, "kette", "Kette", "Texte übersetzen", CHAIN)
    embedder = _FakeEmbedder()
    found = _search("bitte übersetzen", embedder=embedder)
    assert found["method"] == "embedding" and found["results"][0]["title"] == "Kette"
    assert len(embedder.calls[0]) == 2  # both examples embedded once
    _search("noch einmal übersetzen", embedder=embedder)
    assert [len(call) for call in embedder.calls] == [2, 1, 1]  # only the queries since

    def broken(texts):
        raise RuntimeError("Ollama down")

    broken.model = "fake-embed"  # type: ignore[attr-defined]
    assert _search("übersetzen", embedder=broken)["method"] == "keywords"


def test_tool_appears_with_sources_and_uses_the_brief(client, shipped, monkeypatch) -> None:
    _installed(monkeypatch)
    assert "search_examples" not in {tool.name for tool in available_tools()}
    _write(shipped, "kette", "Übersetzer-Kette", "Texte übersetzen", CHAIN)
    assert "search_examples" in {tool.name for tool in available_tools()}
    row = sessions.create("ollama", "qwen3:14b", None)
    session = store.get_session(row.id)
    session.brief = {"goal": "Texte ins Englische übersetzen"}
    store.save_session(session)
    ctx = ToolContext(session=store.get_session(row.id), cloud=False, lookup=app_lookup)
    result = run_tool(available_tools(), ctx, "search_examples", "{}")
    assert result.ok and result.params == {"count": 1}
    status = client.get("/api/architect/examples").json()
    assert (status["count"], status["shipped"], status["method"]) == (1, 1, "keywords")
    rebuilt = client.post("/api/architect/examples/reindex").json()
    assert rebuilt["count"] == 1 and rebuilt["error"] is None


def test_shipped_examples_are_valid_networks() -> None:
    """Drift guard (entwurf.md, 6.4): every shipped example compiles and validates."""
    from app.architect.draft import Lookup
    from app.run.graph_models import AgentNetworkDocument
    from app.run.validate import validate_document

    def validate(document):
        doc = AgentNetworkDocument.model_validate(document)
        return [(e.node_id, e.message_key) for e in validate_document(doc, data_dir="/nonexistent")]

    for path in sorted((catalog_dir() / "examples").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        compiled = compile_draft(raw["draft"], Lookup(validate=validate))
        assert compiled.errors == [], (path.name, [p.text for p in compiled.errors])


def test_settings_switch_turns_own_networks_on(client, shipped, monkeypatch) -> None:
    _installed(monkeypatch)
    client.post("/api/networks", json=compile_draft(CHAIN, app_lookup()).document)
    assert "search_examples" not in {tool.name for tool in available_tools()}
    patch_settings(AppSettingsPatch(architect={"ownNetworksAsExamples": True}))
    assert "search_examples" in {tool.name for tool in available_tools()}
    assert client.post("/api/architect/examples/reindex").json()["own"] == 1
