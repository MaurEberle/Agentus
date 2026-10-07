from __future__ import annotations

from types import SimpleNamespace

from app.run.vram import resident_tags


def test_resident_tags_keep_help_embed_and_current() -> None:
    settings = SimpleNamespace(
        help_chat=SimpleNamespace(
            provider="ollama",
            model="help-chat",
            embedding_provider="ollama",
            embedding_model="help-embed",
        )
    )
    compiled = SimpleNamespace(
        by_id={
            "k": SimpleNamespace(
                type="knowledge",
                data={"embeddingProvider": "ollama", "embeddingModel": "net-embed"},
            )
        }
    )
    keep = resident_tags(settings, compiled, current="writer")
    assert keep == {"writer", "help-chat", "help-embed", "net-embed"}


def test_resident_tags_omit_cloud_help() -> None:
    settings = SimpleNamespace(
        help_chat=SimpleNamespace(
            provider="xai",
            model="grok",
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
        )
    )
    keep = resident_tags(settings, None, current="local")
    assert keep == {"local"}
