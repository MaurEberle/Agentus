from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.help_rag import list_all_chunks
from app.db.networks import list_networks
from app.help.index import corpus_dir
from app.runtime.errors import RuntimeApiError
from app.runtime.models import EmbedResult, StreamEvent
from app.settings.models import AppSettingsPatch
from app.settings.service import patch_settings


def test_send_unconfigured_400(client: TestClient) -> None:
    patch_settings(AppSettingsPatch(help_chat={"provider": "", "model": ""}))
    response = client.post("/api/help-chat/messages", json={"text": "hi"})
    assert response.status_code == 400
    assert response.json()["messageKey"] == "help.unconfigured"


def test_history_hides_stored_think_blocks(client: TestClient) -> None:
    from app.db.engine import utc_now
    from app.db.help_chat import HelpMessageRow, insert_message

    insert_message(
        HelpMessageRow(
            id="old-assistant",
            role="assistant",
            content="<think>intern</think>Sichtbar",
            created_at=utc_now(),
            sources=None,
        )
    )
    insert_message(
        HelpMessageRow(
            id="old-user",
            role="user",
            content="<think>bleibt</think>",
            created_at=utc_now(),
            sources=None,
        )
    )
    items = client.get("/api/help-chat/messages").json()["items"]
    by_id = {item["id"]: item["content"] for item in items}
    assert by_id["old-assistant"] == "Sichtbar"
    assert by_id["old-user"] == "<think>bleibt</think>"


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


def _wait_reindex(client: TestClient, job_id: str | None) -> dict[str, object]:
    body: dict[str, object] = {"state": "running"}
    for _ in range(100):
        body = client.get("/api/help-chat/reindex").json()
        if body["state"] != "running" and (not job_id or body.get("id") == job_id):
            return body
        time.sleep(0.02)
    raise AssertionError(body)


def _finish_reindex(client: TestClient) -> dict[str, object]:
    response = client.post("/api/help-chat/reindex")
    assert response.status_code == 200
    body = response.json()
    if body["state"] != "running":
        return body
    return _wait_reindex(client, body.get("id"))


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
    body = _finish_reindex(client)
    assert body["state"] == "ready"
    assert len(list_all_chunks()) > 0
    assert list_all_chunks()[0].embedding_provider == "ollama"
    assert len(list_networks()) == before_networks


def test_reindex_reports_unsupported_model(client: TestClient, monkeypatch) -> None:
    folder = corpus_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "intro.md").write_text("# Hello\nworld", encoding="utf-8")

    def _embed(req: object) -> EmbedResult:
        del req
        raise RuntimeApiError("runtime.embedUnsupported", status=501)

    monkeypatch.setattr("app.runtime.embeddings.embed", _embed)
    body = _finish_reindex(client)
    assert body["state"] == "error"
    assert body["messageKey"] == "help.embed.runnerFailed"
    assert list_all_chunks() == []


def test_reindex_keeps_running_after_the_request_returns(client: TestClient, monkeypatch) -> None:
    folder = corpus_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "intro.md").write_text("# Hello\nworld", encoding="utf-8")
    started = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    def _embed(req: object) -> EmbedResult:
        texts = getattr(req, "texts", [])
        calls["n"] += 1
        started.set()
        assert release.wait(5)
        return EmbedResult(vectors=[[1.0, 0.0] for _ in texts], dimension=2, model="m")

    monkeypatch.setattr("app.runtime.embeddings.embed", _embed)
    first = client.post("/api/help-chat/reindex")
    assert first.status_code == 200
    assert first.json()["state"] == "running"
    assert started.wait(2)
    second = client.post("/api/help-chat/reindex")
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["state"] == "running"
    assert calls["n"] == 1
    release.set()
    done = _wait_reindex(client, first.json()["id"])
    assert done["state"] == "ready"
    assert calls["n"] == 1


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
