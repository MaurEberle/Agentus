from __future__ import annotations

from app.db import init
from app.llm.downloads import DownloadCreate, enqueue, pause_all, pause_one, remove_downloads, resume_all, resume_one


def test_queue_keeps_one_active_slot_and_a_global_gate(api_env) -> None:
    init()
    first = enqueue(DownloadCreate(model="hf.co/acme/Model-GGUF:Q4_K_M", label="Model", size_bytes=10))
    second = enqueue(DownloadCreate(model="hf.co/acme/Other-GGUF:Q4_K_M", label="Other", publisher="acme"))
    assert [item.label for item in second.items] == ["Model", "Other"]
    assert all(item.status == "queued" for item in second.items)
    again = enqueue(DownloadCreate(model="hf.co/acme/Model-GGUF:Q4_K_M", label="Model"))
    assert len(again.items) == 2

    paused = pause_one(first.items[0].id)
    assert next(item for item in paused.items if item.label == "Model").status == "paused"
    resumed = resume_one(first.items[0].id)
    assert resumed.items[0].label == "Model"
    assert resumed.items[0].status == "queued"

    gate = pause_all()
    assert gate.paused is True
    opened = resume_all()
    assert opened.paused is False
    pause_one(opened.items[0].id)
    pause_one(opened.items[1].id)
    started = resume_all()
    assert started.paused is False
    assert {item.status for item in started.items} == {"queued"}
    removed = remove_downloads([item.id for item in opened.items])
    assert removed.items == []
