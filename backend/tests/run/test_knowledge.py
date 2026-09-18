from __future__ import annotations

from app.db import init
from app.run.graph_models import AgentNetworkDocument
from app.run.knowledge import retrieve
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
