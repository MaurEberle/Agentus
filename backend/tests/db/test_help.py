from __future__ import annotations

from app.db import init
from app.db.help_chat import HelpMessageRow, clear_messages, insert_message, list_messages
from app.db.help_rag import HelpRagChunk, list_all_chunks, replace_all_chunks, wipe_chunks


def test_help_messages_order_and_clear() -> None:
    init()
    insert_message(
        HelpMessageRow(
            id="m1",
            role="user",
            content="hi",
            created_at="2026-01-01T00:00:00+00:00",
            sources=None,
        )
    )
    insert_message(
        HelpMessageRow(
            id="m2",
            role="assistant",
            content="hello",
            created_at="2026-01-01T00:00:01+00:00",
            sources=[{"title": "doc"}],
        )
    )
    rows = list_messages()
    assert [row.id for row in rows] == ["m1", "m2"]
    assert rows[1].sources == [{"title": "doc"}]
    clear_messages()
    assert list_messages() == []


def test_help_rag_replace_and_wipe() -> None:
    init()
    replace_all_chunks(
        [
            HelpRagChunk(
                id="h1",
                source="help.md",
                section="intro",
                text="usage",
                file_hash="1",
                embedding=[1.0, 0.0],
                embedding_model_id="nomic-embed-text",
                dimension=2,
            )
        ]
    )
    assert len(list_all_chunks()) == 1
    wipe_chunks()
    assert list_all_chunks() == []
