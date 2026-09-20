from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.db.help_rag import list_all_chunks
from app.db.networks import list_networks
from app.help.index import corpus_dir
from app.runtime.models import EmbedResult, StreamEvent
from app.settings.models import AppSettingsPatch
from app.settings.service import patch_settings


def test_send_unconfigured_400(client: TestClient) -> None:
    patch_settings(AppSettingsPatch(help_chat={"provider": "", "model": ""}))
    response = client.post("/api/help-chat/messages", json={"text": "hi"})
    assert response.status_code == 400
    assert response.json()["messageKey"] == "help.unconfigured"


def test_clear(client: TestClient, monkeypatch) -> None:
    from app.db.help_rag import HelpRagChunk, replace_all_chunks

    replace_all_chunks(
        [
            HelpRagChunk(
                id="1",
                source="g",
                section=None,
                text="t",
                file_hash="h",
                embedding=[1.0],
                embedding_model_id="m",
                dimension=1,
            )
        ]
    )
    monkeypatch.setattr(
        "app.help.pipeline.retrieve_scored",
        lambda q, locale=None: [],
    )
    monkeypatch.setattr(
        "app.runtime.completions.complete_stream",
        lambda req: iter([StreamEvent(kind="delta", text="x"), StreamEvent(kind="done")]),
    )
    client.post("/api/help-chat/messages", json={"text": "hello"})
    listed = client.get("/api/help-chat/messages")
    assert listed.status_code == 200
    assert listed.json()["items"]
    cleared = client.post("/api/help-chat/clear")
    assert cleared.status_code == 204
    assert client.get("/api/help-chat/messages").json()["items"] == []


def test_reindex_tmp_md(client: TestClient, monkeypatch) -> None:
    folder = corpus_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "intro.md").write_text("# Hello\nworld", encoding="utf-8")
    monkeypatch.setattr(
        "app.runtime.embeddings.embed",
        lambda req: EmbedResult(
            vectors=[[1.0, 0.0] for _ in req.texts],
            dimension=2,
            model=req.model,
        ),
    )
    before_networks = len(list_networks())
    response = client.post("/api/help-chat/reindex")
    assert response.status_code == 200
    assert response.json()["state"] == "ready"
    assert len(list_all_chunks()) > 0
    assert len(list_networks()) == before_networks


def test_status_and_ping(client: TestClient, monkeypatch) -> None:
    status = client.get("/api/help-chat/status")
    assert status.status_code == 200
    assert "configured" in status.json()
    monkeypatch.setattr(
        "app.runtime.completions.test_llm",
        lambda req: __import__("app.runtime.models", fromlist=["PingResult"]).PingResult(ok=True),
    )
    ping = client.post("/api/help-chat/ping")
    assert ping.status_code == 200
    assert ping.json()["ok"] is True


def test_no_mcp_import() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "help"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "app.mcp" in text or "app.db.network_rag" in text:
            offenders.append(str(path))
    assert offenders == []
