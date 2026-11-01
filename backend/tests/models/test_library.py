from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.engine import utc_now
from app.db.networks import NetworkRow, upsert_network
from app.db.settings import put_settings
from app.llm.catalog import huggingface_url, model_kind
from app.llm.hub import keep_hub_row, quant_token, valid_pull_model
from app.llm.usage import model_usages


def test_kind_uses_name_and_ollama_metadata() -> None:
    vl = "hf.co/bealore/Qwen3-VL-Embedding-2B-GGUF:Q8_0"
    vl_info = {"general.architecture": "qwen3vl", "qwen3vl.embedding_length": 2048}
    assert model_kind(vl, ["tools", "completion", "vision"], moe=False, info=vl_info) == "embedding"
    chat_info = {"general.architecture": "llama", "llama.embedding_length": 2048}
    assert model_kind("llama3.2:1b", ["completion", "tools"], moe=False, info=chat_info) == "normal"
    pooled = {"nomic-bert.pooling_type": 1, "nomic-bert.embedding_length": 768}
    assert model_kind("custom-encoder", ["completion"], moe=False, info=pooled) == "embedding"
    assert model_kind("chat", ["embedding"], moe=False) == "embedding"
    assert model_kind("chat", ["completion", "vision"], moe=True) == "moe"
    assert model_kind("painter", ["image"], moe=False) == "image"
    assert model_kind("embed-painter", ["image"], moe=False) == "image"
    assert model_kind("nomic-embed-text", [], moe=False) == "embedding"


def test_huggingface_url_strips_the_quant() -> None:
    assert huggingface_url("hf.co/bartowski/Llama-GGUF:Q4_K_M") == (
        "https://huggingface.co/bartowski/Llama-GGUF"
    )
    assert huggingface_url("llama3.2:1b") is None
    assert huggingface_url("hf.co/../secret") is None


def test_quant_token_and_pull_name() -> None:
    assert quant_token("Llama-3.2-1B-Instruct-Q4_K_M.gguf") == "Q4_K_M"
    assert valid_pull_model("hf.co/bartowski/Llama-GGUF:Q4_K_M")
    assert not valid_pull_model("llama3.2:1b")
    assert not valid_pull_model("hf.co/bartowski/Llama-GGUF")


def test_hub_row_drops_gated_and_other_tasks() -> None:
    row = {"id": "a/b", "modelId": "a/b", "pipeline_tag": "text-generation", "gated": False}
    assert keep_hub_row(row, ("text-generation",))
    assert not keep_hub_row({**row, "gated": True}, ("text-generation",))
    assert not keep_hub_row({**row, "pipeline_tag": "text-to-image"}, ("text-generation",))


def test_usage_matches_latest_alias_network_and_help(api_env) -> None:
    from app.db import init

    init()
    put_settings({"helpChat": {"embeddingModel": "nomic-embed-text:latest"}})
    upsert_network(
        NetworkRow(
            id="net-1",
            name="TestWriter",
            description=None,
            tags=[],
            document={
                "nodes": [
                    {
                        "id": "llm-1",
                        "type": "llm",
                        "data": {"model": "hf.co/acme/Model-GGUF:Q4_K_M", "displayName": "Schreiber"},
                    }
                ]
            },
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    embed = model_usages("nomic-embed-text")
    assert embed == [{"kind": "help.embed"}]
    used = model_usages("hf.co/acme/Model-GGUF:Q4_K_M")
    assert used == [{"kind": "network", "network": "TestWriter", "node": "Schreiber"}]
    assert model_usages("other:latest") == []


def test_delete_is_blocked_while_a_network_uses_the_model(client: TestClient) -> None:
    from app.db.engine import utc_now as stamp

    upsert_network(
        NetworkRow(
            id="net-2",
            name="Story",
            description=None,
            tags=[],
            document={"nodes": [{"id": "llm-2", "type": "llm", "data": {"model": "llama3.2:latest"}}]},
            updated_at=stamp(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    response = client.post("/api/models/delete", json={"name": "llama3.2"})
    assert response.status_code == 409
    body = response.json()
    assert body["messageKey"] == "models.inUse"
    assert body["usages"][0]["kind"] == "network"
    assert body["usages"][0]["network"] == "Story"
