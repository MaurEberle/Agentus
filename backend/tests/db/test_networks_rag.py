from __future__ import annotations

import pytest

from app.db import init
from app.db.engine import utc_now
from app.db.network_rag import (
    CollectionMeta,
    RagChunk,
    list_chunks,
    list_collection_states,
    replace_chunks,
    upsert_collection,
)
from app.db.networks import (
    NetworkRow,
    delete_network,
    duplicate_network,
    get_network,
    list_networks,
    upsert_network,
)
from app.db.runs import get_run, insert_run


def _net(network_id: str, name: str = "Demo") -> NetworkRow:
    return NetworkRow(
        id=network_id,
        name=name,
        description=None,
        tags=["demo"],
        document={"id": network_id, "schemaVersion": 1, "nodes": [], "edges": []},
        updated_at=utc_now(),
        last_used_at=None,
        last_run_id=None,
    )


def _seed_rag(network_id: str) -> None:
    upsert_collection(
        CollectionMeta(
            network_id=network_id,
            node_id="kn-1",
            source_path="C:\\docs",
            embedding_model_id="nomic-embed-text",
            dimension=2,
            state="ready",
            updated_at=utc_now(),
        )
    )
    replace_chunks(
        network_id,
        "kn-1",
        [
            RagChunk(
                id="chunk-a",
                network_id=network_id,
                node_id="kn-1",
                source="a.md",
                section=None,
                text="hello",
                file_hash="abc",
                embedding=[0.25, 0.5],
                embedding_model_id="nomic-embed-text",
                dimension=2,
            )
        ],
    )


def test_delete_network_clears_rag_keeps_history() -> None:
    init()
    upsert_network(_net("net-1"))
    _seed_rag("net-1")
    insert_run(
        id="run-1",
        network_id="net-1",
        network_name="Demo",
        started_at=utc_now(),
        outcome="succeeded",
    )
    delete_network("net-1")
    assert get_network("net-1") is None
    assert list_collection_states("net-1") == []
    assert list_chunks("net-1", "kn-1") == []
    assert get_run("run-1") is not None
    assert get_run("run-1")["network_id"] == "net-1"


def test_duplicate_copies_rag_with_new_chunk_ids() -> None:
    init()
    upsert_network(_net("net-1"))
    _seed_rag("net-1")
    copied = duplicate_network("net-1", "net-2", "Demo copy")
    assert copied.id == "net-2"
    assert copied.name == "Demo copy"
    assert copied.document["id"] == "net-2"
    assert get_network("net-1") is not None
    assert len(list_networks()) == 2
    old_chunks = list_chunks("net-1", "kn-1")
    new_chunks = list_chunks("net-2", "kn-1")
    assert len(old_chunks) == len(new_chunks) == 1
    assert old_chunks[0].id != new_chunks[0].id
    assert new_chunks[0].text == "hello"
    assert new_chunks[0].embedding == pytest.approx(old_chunks[0].embedding)
    states = list_collection_states("net-2")
    assert len(states) == 1
    assert states[0].node_id == "kn-1"
