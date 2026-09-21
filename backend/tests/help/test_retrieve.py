from __future__ import annotations

from app.db import init
from app.db.help_rag import HelpRagChunk, replace_all_chunks
from app.help.retrieve import retrieve
from app.runtime.models import EmbedRequest, EmbedResult
from app.settings.models import AppSettingsPatch
from app.settings.service import patch_settings


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


def test_retrieve_uses_stored_model_not_unsaved_settings(api_env, monkeypatch) -> None:
    init()
    patch_settings(
        AppSettingsPatch(
            help_chat={
                "embeddingProvider": "ollama",
                "embeddingModel": "hf.co/bealore/Qwen3-VL-Embedding-2B-GGUF:Q8_0",
            }
        )
    )
    replace_all_chunks(
        [
            HelpRagChunk(
                id="1",
                source="alpha",
                section=None,
                text="aaa",
                file_hash="h",
                embedding=[1.0, 0.0],
                embedding_model_id="hf.co/mradermacher/Qwen3-Embedding-0.6B-GGUF:Q4_K_M",
                dimension=2,
                locale="de",
            )
        ]
    )
    captured: list[EmbedRequest] = []

    def _embed(req: EmbedRequest) -> EmbedResult:
        captured.append(req)
        return EmbedResult(vectors=[[1.0, 0.0]], dimension=2, model=req.model)

    monkeypatch.setattr("app.runtime.embeddings.embed", _embed)
    hits = retrieve("query", locale="de")
    assert hits[0].title == "alpha"
    assert captured[0].model == "hf.co/mradermacher/Qwen3-Embedding-0.6B-GGUF:Q4_K_M"
    assert captured[0].provider == "ollama"
