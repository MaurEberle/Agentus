from __future__ import annotations

from app.db import init
from app.db.help_rag import HelpRagChunk, replace_all_chunks
from app.help.retrieve import retrieve
from app.runtime.models import EmbedResult


def test_retrieve_top_title(api_env, monkeypatch) -> None:
    init()
    replace_all_chunks(
        [
            HelpRagChunk(
                id="1",
                source="alpha",
                section="intro",
                text="aaa",
                file_hash="h",
                embedding=[1.0, 0.0],
                embedding_model_id="nomic-embed-text",
                dimension=2,
            ),
            HelpRagChunk(
                id="2",
                source="beta",
                section=None,
                text="bbb",
                file_hash="h",
                embedding=[0.0, 1.0],
                embedding_model_id="nomic-embed-text",
                dimension=2,
            ),
        ]
    )
    monkeypatch.setattr(
        "app.runtime.embeddings.embed",
        lambda req: EmbedResult(vectors=[[1.0, 0.0]], dimension=2, model=req.model),
    )
    hits = retrieve("query")
    assert hits[0].title == "alpha"
    assert hits[0].kind == "rag"


def test_retrieve_filters_by_locale(api_env, monkeypatch) -> None:
    init()
    replace_all_chunks(
        [
            HelpRagChunk(
                id="1",
                source="de-guide",
                section="intro",
                text="aaa",
                file_hash="h",
                embedding=[1.0, 0.0],
                embedding_model_id="nomic-embed-text",
                dimension=2,
                locale="de",
            ),
            HelpRagChunk(
                id="2",
                source="fr-guide",
                section="intro",
                text="aaa",
                file_hash="h",
                embedding=[1.0, 0.0],
                embedding_model_id="nomic-embed-text",
                dimension=2,
                locale="fr",
            ),
        ]
    )
    monkeypatch.setattr(
        "app.runtime.embeddings.embed",
        lambda req: EmbedResult(vectors=[[1.0, 0.0]], dimension=2, model=req.model),
    )
    french = retrieve("query", locale="fr")
    assert [hit.title for hit in french] == ["fr-guide"]
    german = retrieve("query", locale="de")
    assert [hit.title for hit in german] == ["de-guide"]
