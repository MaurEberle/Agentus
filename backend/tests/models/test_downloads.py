from __future__ import annotations

from app.db import init
from app.db.engine import transaction
from app.llm.blobs import discard_blob_files, parse_manifest_digests
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
    removed = remove_downloads([item.id for item in started.items])
    assert removed.items == []


def test_remove_deletes_partial_blobs(api_env, tmp_path, monkeypatch) -> None:
    init()
    digest = "sha256:" + "ab" * 32
    stem = digest.replace(":", "-")
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    (blobs / f"{stem}-partial").write_bytes(b"partial")
    (blobs / f"{stem}-partial-0").write_text("{}", encoding="utf-8")
    (blobs / stem).write_bytes(b"finished")
    kept = "sha256:" + "cd" * 32
    kept_stem = kept.replace(":", "-")
    (blobs / kept_stem).write_bytes(b"shared")
    manifest = tmp_path / "manifests" / "registry.ollama.ai" / "library" / "other" / "latest"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"layers":[{"digest":"%s"}]}' % kept, encoding="utf-8")
    monkeypatch.setattr("app.llm.downloads.fetch_manifest_digests", lambda _model: [digest])
    monkeypatch.setattr("app.llm.downloads.discard_blob_files", lambda digests, root=None: discard_blob_files(digests, root=tmp_path))
    monkeypatch.setattr("app.llm.downloads._forget_installed", lambda _model: None)
    created = enqueue(DownloadCreate(model="hf.co/acme/Model-GGUF:Q4_K_M", label="Model"))
    remove_downloads([created.items[0].id])
    names = sorted(path.name for path in blobs.iterdir())
    assert names == [kept_stem]
    assert parse_manifest_digests({"config": {"digest": digest}, "layers": [{"digest": kept}]}) == [digest, kept]


def test_remove_finished_keeps_the_model_files(api_env, tmp_path, monkeypatch) -> None:
    init()
    digest = "sha256:" + "ef" * 32
    stem = digest.replace(":", "-")
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    (blobs / stem).write_bytes(b"model")
    (blobs / f"{stem}-partial").write_bytes(b"partial")
    monkeypatch.setattr("app.llm.downloads.fetch_manifest_digests", lambda _model: [digest])
    monkeypatch.setattr(
        "app.llm.downloads.discard_blob_files",
        lambda digests, root=None: (_ for _ in ()).throw(AssertionError("finished download must keep its files")),
    )
    monkeypatch.setattr(
        "app.llm.downloads._forget_installed",
        lambda _model: (_ for _ in ()).throw(AssertionError("finished model must stay installed")),
    )
    created = enqueue(DownloadCreate(model="hf.co/acme/Model-GGUF:Q4_K_M", label="Model"))
    with transaction("workspace") as conn:
        conn.execute("UPDATE model_downloads SET status = 'done' WHERE id = ?", (created.items[0].id,))
    removed = remove_downloads([created.items[0].id])
    assert removed.items == []
    assert sorted(path.name for path in blobs.iterdir()) == [stem, f"{stem}-partial"]
