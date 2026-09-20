from __future__ import annotations

from pathlib import Path

from app.db import init
from app.db.bootstrap import load_bootstrap
from app.run.graph_models import AgentNetworkDocument, GraphNode
from app.run.knowledge import index_node, retrieve
from app.run.compile import compile_document
from app.run.controller import get_controller
from app.db.networks import NetworkRow, upsert_network
from app.db.engine import utc_now
from app.settings.models import AppSettingsPatch
from app.settings.service import patch_settings
from tests.run.conftest import mini_doc


def test_retrieve_before_complete_adds_context(monkeypatch, api_env) -> None:
    init()
    captured: list[str] = []

    def _complete(req):
        from app.runtime.models import CompletionResult

        captured.append(req.messages[0].content or "")
        return CompletionResult(content="hi", model=req.model, finish_reason="stop")

    monkeypatch.setattr("app.runtime.completions.complete", _complete)
    monkeypatch.setattr(
        "app.run.harness.retrieve",
        lambda *a, **k: [
            __import__("app.run.knowledge", fromlist=["Snippet"]).Snippet(
                title="doc", section="s", text="secret snippet", score=1.0
            )
        ],
    )
    doc = mini_doc(startMessage="q")
    upsert_network(
        NetworkRow(
            id="net-1",
            name="mini",
            description=None,
            tags=[],
            document=doc,
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    patch_settings(AppSettingsPatch(active_network_id="net-1"))
    get_controller().start()
    thread = get_controller().thread
    if thread:
        thread.join(timeout=5)
    assert captured
    assert "secret snippet" in captured[0] or "No document context." in captured[0]


def test_index_uses_node_embedding_settings(monkeypatch, api_env) -> None:
    from app.runtime.models import EmbedRequest, EmbedResult

    init()
    captured: list[EmbedRequest] = []

    def _embed(req: EmbedRequest) -> EmbedResult:
        captured.append(req)
        return EmbedResult(
            vectors=[[0.1, 0.2] for _ in req.texts],
            dimension=2,
            model=req.model,
        )

    monkeypatch.setattr("app.runtime.embeddings.embed", _embed)
    upsert_network(
        NetworkRow(
            id="net-1",
            name="kb",
            description=None,
            tags=[],
            document={"schemaVersion": 1, "name": "kb", "nodes": [], "edges": []},
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    data_dir = load_bootstrap().data_dir
    folder = Path(data_dir) / "kb"
    folder.mkdir(parents=True)
    (folder / "note.md").write_text("# Hello\nworld", encoding="utf-8")
    node = GraphNode(
        id="k1",
        type="knowledge",
        position={"x": 0, "y": 0},
        data={
            "sourcePath": str(folder),
            "embeddingProvider": "openai",
            "embeddingModel": "text-embedding-3-small",
            "embeddingCredentialId": "cred-1",
        },
    )
    assert index_node("net-1", node, data_dir=str(data_dir), force=True) == "ready"
    assert captured
    assert captured[0].model == "text-embedding-3-small"
    assert captured[0].provider == "openai"
    assert captured[0].credential_id == "cred-1"
