from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.engine import utc_now
from app.db.networks import NetworkRow, upsert_network
from app.db.settings import put_settings
from app.llm.catalog import huggingface_url, model_kind
from app.llm.hub import (
    HubHit,
    format_parameter_count,
    keep_hub_row,
    keep_weight_file,
    order_hits,
    parameter_label,
    parameter_query,
    pipeline_tags,
    quant_token,
    template_flags,
    valid_pull_model,
)
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


def test_name_sort_orders_the_page() -> None:
    hits = [
        HubHit(id="hf.co/zzz/Alpha:Q8_0", url="https://huggingface.co/zzz/Alpha"),
        HubHit(id="hf.co/aaa/beta", url="https://huggingface.co/aaa/beta"),
        HubHit(id="nomic-embed-text:latest", url="https://ollama.com/library/nomic-embed-text"),
    ]
    order_hits(hits, "name", ascending=True)
    assert [item.id for item in hits] == [
        "hf.co/zzz/Alpha:Q8_0",
        "hf.co/aaa/beta",
        "nomic-embed-text:latest",
    ]
    order_hits(hits, "name", ascending=False)
    assert [item.id for item in hits] == [
        "nomic-embed-text:latest",
        "hf.co/aaa/beta",
        "hf.co/zzz/Alpha:Q8_0",
    ]
    order_hits(hits, "downloads", ascending=True)
    assert [item.id for item in hits] == [
        "hf.co/zzz/Alpha:Q8_0",
        "hf.co/aaa/beta",
        "nomic-embed-text:latest",
    ]


def test_parameter_label_uses_the_weight_count() -> None:
    assert format_parameter_count(27_009_346_304) == "27B"
    assert format_parameter_count(1_720_000_000) == "1.72B"
    assert format_parameter_count(29_900_000_000) == "29.9B"
    assert format_parameter_count(307_581_696) == "308M"
    assert parameter_label({"gguf": {"total": 27_009_346_304}}) == "27B"
    assert parameter_label({"safetensors": {"total": 596_000_000}}) == "596M"
    assert parameter_label({}) is None


def test_pipeline_tags_cover_every_type_when_unset() -> None:
    assert pipeline_tags("") == (
        "text-generation",
        "feature-extraction",
        "sentence-similarity",
        "image-text-to-text",
    )
    assert pipeline_tags("all") == pipeline_tags("")
    assert pipeline_tags("text,vision") == ("text-generation", "image-text-to-text")
    assert pipeline_tags("embed") == ("feature-extraction", "sentence-similarity")


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


def test_capability_filter_parses_known_names() -> None:
    from app.llm.hub import HubHit, _matches, parse_capabilities

    assert parse_capabilities("tools, thinking, nope") == ("tools", "thinking")
    hit = HubHit(id="a/b", url="https://huggingface.co/a/b", tools=True, thinking=False, vision=False)
    assert _matches(hit, ("tools",))
    assert not _matches(hit, ("tools", "thinking"))


def test_page_marks_and_cursor_link() -> None:
    from app.llm.hub import cursor_from_link, pack_cursors, page_limit, unpack_cursors

    assert page_limit(30) == 30
    assert page_limit(1) == 10
    assert page_limit(1000) == 100
    assert page_limit(40) in {30, 50}
    header = '<https://huggingface.co/api/models?limit=10&cursor=abc%2Bdef>; rel="next"'
    assert cursor_from_link(header) == "abc+def"
    assert cursor_from_link(None) is None
    packed = pack_cursors(["one", None])
    assert packed is not None and packed.startswith("v1.")
    assert unpack_cursors(packed, 2) == ["one", None]
    assert unpack_cursors(None, 2) is None


def test_parameter_query_accepts_decimal_billions() -> None:
    assert parameter_query("any") is None
    assert parameter_query("3") == "max:3B"
    assert parameter_query("min:0.6B,max:4B") == "min:0.6B,max:4B"
    assert parameter_query("max:0.6B") == "max:0.6B"
    assert parameter_query("min:0.6B,max:nope") is None
    assert parameter_query("min:0,6B") is None


def test_weight_files_skip_imatrix_and_projectors() -> None:
    assert keep_weight_file("model-Q4_K_M.gguf")
    assert not keep_weight_file("imatrix-swift15-v1mix.gguf")
    assert not keep_weight_file("mmproj-model.gguf")
    assert not keep_weight_file("README.md")


def test_card_flags_match_the_detail_rules() -> None:
    from app.llm.hub import flags_from_card

    tools, thinking, vision = flags_from_card(
        {
            "pipeline_tag": "text-generation",
            "tags": ["conversational"],
            "gguf": {"chat_template": "use tool_call and <think>"},
        }
    )
    assert (tools, thinking, vision) == (True, True, False)
    assert flags_from_card({"pipeline_tag": "image-text-to-text", "gguf": {}})[2] is True


def test_template_flags_read_tools_and_thinking() -> None:
    tools, thinking = template_flags("call tool_call then <think>", ["conversational"])
    assert tools is True
    assert thinking is True
    tools, thinking = template_flags("hello", ["reasoning"])
    assert tools is False
    assert thinking is True
    assert template_flags("", []) == (False, False)


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
