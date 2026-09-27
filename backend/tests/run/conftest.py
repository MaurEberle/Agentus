from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import init, reset
from app.db.vault import reset_memory, use_memory
from app.http.app import create_app
from app.run.controller import get_controller
from app.runtime.models import CompletionResult, EmbedResult, OllamaModel
from app.settings.in_use import reset_mcp_usage_provider
from app.tools.catalog import reset_mcp_catalog_provider


unloads: list[str] = []


def mini_doc(**chat: object) -> dict:
    data = dict(chat) if chat else {}
    return {
        "schemaVersion": 1,
        "name": "mini",
        "nodes": [
            {"id": "in", "type": "chat_input", "position": {"x": 0, "y": 0}, "data": data},
            {
                "id": "llm",
                "type": "llm",
                "position": {"x": 0, "y": 0},
                "data": {"provider": "ollama", "model": "llama3.2:1b"},
            },
            {"id": "ag", "type": "agent", "position": {"x": 0, "y": 0}, "data": {"systemPrompt": "sys"}},
            {"id": "end", "type": "end", "position": {"x": 0, "y": 0}, "data": {}},
        ],
        "edges": [
            {
                "id": "e1",
                "source": "in",
                "sourceHandle": "message",
                "target": "ag",
                "targetHandle": "message",
            },
            {
                "id": "e2",
                "source": "llm",
                "sourceHandle": "llm",
                "target": "ag",
                "targetHandle": "llm",
            },
            {
                "id": "e3",
                "source": "ag",
                "sourceHandle": "message",
                "target": "end",
                "targetHandle": "message",
            },
        ],
    }


@pytest.fixture
def api_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTUS_NETWORK_VAULT", "memory")
    reset()
    use_memory()
    reset_memory()
    reset_mcp_catalog_provider()
    reset_mcp_usage_provider()
    get_controller().reset()
    unloads.clear()
    monkeypatch.setattr("app.runtime.ollama.ensure_loaded", lambda *a, **k: None)
    monkeypatch.setattr("app.run.window.loaded_context", lambda *a, **k: None)
    monkeypatch.setattr("app.run.window.architecture_context", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.runtime.ollama.list_ollama_models",
        lambda *a, **k: [OllamaModel(name="llama3.2:1b", size_bytes=None)],
    )
    monkeypatch.setattr("app.runtime.ollama.unload", lambda *a, **k: unloads.append(a[0] if a else ""))
    def _complete(req, should_abort=None, on_progress=None):
        return CompletionResult(content="hi", model=req.model, finish_reason="stop")

    monkeypatch.setattr("app.runtime.completions.complete", _complete)
    monkeypatch.setattr("app.runtime.completions.complete_live", _complete)
    monkeypatch.setattr(
        "app.runtime.embeddings.embed",
        lambda req: EmbedResult(
            vectors=[[1.0, 0.0] for _ in req.texts],
            dimension=2,
            model=req.model,
        ),
    )
    yield tmp_path
    get_controller().reset()
    reset()
    reset_memory()


@pytest.fixture
def client(api_env) -> TestClient:
    init()
    return TestClient(create_app())
