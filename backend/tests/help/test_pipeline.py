from __future__ import annotations

from app.db import init
from app.db.help_rag import HelpRagChunk, replace_all_chunks
from app.db.vault import put
from app.help.abort import abort_current
from app.help.models import HelpSource
from app.help.pipeline import send_stream
from app.help.status import set_degraded
from app.runtime.models import CompletionRequest, StreamEvent
from app.settings.models import AppSettingsPatch
from app.settings.service import patch_settings
from app.tools.models import ExecuteResult


def _ready_index() -> None:
    replace_all_chunks(
        [
            HelpRagChunk(
                id="1",
                source="guide",
                section="start",
                text="hello",
                file_hash="h",
                embedding=[1.0, 0.0],
                embedding_model_id="nomic-embed-text",
                dimension=2,
            )
        ]
    )


def _parse(events: list[bytes]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for raw in events:
        text = raw.decode("utf-8")
        name = ""
        data = ""
        for line in text.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            if line.startswith("data:"):
                data = line[5:].strip()
        out.append((name, data))
    return out


def test_no_web_when_disabled(api_env, monkeypatch) -> None:
    init()
    _ready_index()
    patch_settings(AppSettingsPatch(help_chat={"webSearchEnabled": False}))
    called = {"web": 0}

    def _web(*args, **kwargs):
        called["web"] += 1
        return ExecuteResult(ok=True, result={"results": []})

    monkeypatch.setattr("app.tools.execute.execute_first_party", _web)
    from app.runtime.models import EmbedResult

    monkeypatch.setattr(
        "app.runtime.embeddings.embed",
        lambda req: EmbedResult(vectors=[[1.0, 0.0]], dimension=2, model="nomic-embed-text"),
    )
    monkeypatch.setattr(
        "app.runtime.completions.complete_stream",
        lambda req: iter([StreamEvent(kind="delta", text="ok"), StreamEvent(kind="done")]),
    )
    parsed = _parse(list(send_stream("hello")))
    kinds = [name for name, _ in parsed]
    assert "sources" in kinds
    assert called["web"] == 0
    assert "web" not in parsed[0][1]


def test_web_after_weak_rag(api_env, monkeypatch) -> None:
    init()
    _ready_index()
    put("web-1", "brave-secret")
    patch_settings(
        AppSettingsPatch(
            help_chat={"webSearchEnabled": True, "webSearchCredentialId": "web-1"}
        )
    )
    order: list[str] = []

    def _retrieve(query: str):
        order.append("rag")
        return []

    def _web(kind, **kwargs):
        order.append("web")
        assert kind == "web_search"
        return ExecuteResult(
            ok=True,
            result={"results": [{"title": "Hit", "url": "https://example.com", "snippet": "s"}]},
        )

    monkeypatch.setattr("app.help.pipeline.retrieve_scored", _retrieve)
    monkeypatch.setattr("app.tools.execute.execute_first_party", _web)
    captured: list[CompletionRequest] = []

    def _stream(req: CompletionRequest):
        captured.append(req)
        yield StreamEvent(kind="delta", text="ans")
        yield StreamEvent(kind="done")

    monkeypatch.setattr("app.runtime.completions.complete_stream", _stream)
    parsed = _parse(list(send_stream("question")))
    assert order == ["rag", "web"]
    assert '"kind": "web"' in parsed[0][1]
    assert parsed[0][0] == "sources"


def test_abort_done_partial(api_env, monkeypatch) -> None:
    init()
    _ready_index()
    monkeypatch.setattr("app.help.pipeline.retrieve_scored", lambda q: [(1.0, HelpSource(kind="rag", title="g"))])

    def _stream(req: CompletionRequest):
        yield StreamEvent(kind="delta", text="hi")
        abort_current()
        yield StreamEvent(kind="delta", text="there")
        yield StreamEvent(kind="done")

    monkeypatch.setattr("app.runtime.completions.complete_stream", _stream)
    parsed = _parse(list(send_stream("q")))
    names = [n for n, _ in parsed]
    assert "done" in names
    assert "500" not in "".join(d for _, d in parsed)
    done = next(d for n, d in parsed if n == "done")
    assert "hi" in done
    assert "there" not in done


def test_degraded_uses_fallback(api_env, monkeypatch) -> None:
    init()
    _ready_index()
    set_degraded(True)
    captured: list[CompletionRequest] = []

    def _stream(req: CompletionRequest):
        captured.append(req)
        yield StreamEvent(kind="done")

    monkeypatch.setattr("app.help.pipeline.retrieve_scored", lambda q: [(1.0, HelpSource(kind="rag", title="g"))])
    monkeypatch.setattr("app.runtime.completions.complete_stream", _stream)
    list(send_stream("q"))
    assert captured[0].model == "llama3.2:1b"
    assert captured[0].ollama_options == {"num_gpu": 0}


def test_masked_secret_persisted(api_env, monkeypatch) -> None:
    init()
    _ready_index()
    monkeypatch.setattr("app.help.pipeline.retrieve_scored", lambda q: [(1.0, HelpSource(kind="rag", title="g"))])
    monkeypatch.setattr(
        "app.runtime.completions.complete_stream",
        lambda req: iter([StreamEvent(kind="done")]),
    )
    list(send_stream("key sk-abcdefghijkl"))
    from app.db.help_chat import list_messages

    stored = list_messages()
    assert any("sk-***" in row.content for row in stored)
    assert all("sk-abcdefghijkl" not in row.content for row in stored)
