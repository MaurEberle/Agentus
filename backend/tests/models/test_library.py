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
    parameter_label,
    hf_sort_key,
    parameter_query,
    pipeline_tags,
    quant_token,
    template_flags,
    type_selection,
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


def test_parameter_label_uses_the_weight_count() -> None:
    assert format_parameter_count(27_009_346_304) == "27B"
    assert format_parameter_count(1_720_000_000) == "1.72B"
    assert format_parameter_count(29_900_000_000) == "29.9B"
    assert format_parameter_count(307_581_696) == "308M"
    assert parameter_label({"gguf": {"total": 27_009_346_304}}) == "27B"
    assert parameter_label({"safetensors": {"total": 596_000_000}}) == "596M"
    assert parameter_label({}) is None


def test_hub_sort_keys_match_the_api() -> None:
    assert hf_sort_key("downloads") == "downloads"
    assert hf_sort_key("likes") == "likes"
    assert hf_sort_key("trending") == "trendingScore"
    assert hf_sort_key("modified") == "lastModified"
    assert hf_sort_key("name") == "downloads"
    assert hf_sort_key("new") == "createdAt"


def test_pipeline_tags_cover_every_type_when_unset() -> None:
    assert pipeline_tags("") == (
        "text-generation",
        "image-text-to-text",
        "feature-extraction",
        "sentence-similarity",
    )
    # Chat models, those that also see included; "Sehen" decides about the latter.
    assert pipeline_tags("text") == ("text-generation", "image-text-to-text")
    assert pipeline_tags("all") == pipeline_tags("")
    assert pipeline_tags("text,vision") == ("text-generation", "image-text-to-text")
    assert pipeline_tags("embed") == ("feature-extraction", "sentence-similarity")
    assert pipeline_tags("moe") == pipeline_tags("")
    assert type_selection("text,moe") == ("text", True)
    assert type_selection("moe") == ("", True)
    assert type_selection("text") == ("text", False)


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
    from app.llm.hub import HubHit, _matches, capability_filter, parse_capabilities

    assert parse_capabilities("tools, thinking, nope") == ("tools", "thinking")
    hit = HubHit(id="a/b", url="https://huggingface.co/a/b", tools=True, thinking=False, vision=False)
    assert _matches(hit, ("tools",))
    assert not _matches(hit, ("tools", "thinking"))
    assert _matches(hit, ("tools",), ("thinking",))
    assert not _matches(hit, (), ("tools",))
    # Asked for both ways, "must not" wins.
    assert capability_filter("tools,thinking", "thinking") == (("tools",), ("thinking",))


def test_vision_is_filtered_by_task() -> None:
    from app.llm.hub import narrow_pipelines

    every = pipeline_tags("all")
    assert narrow_pipelines(every, ("vision", "tools"), ()) == (("image-text-to-text",), ("tools",), ())
    pipes, must, never = narrow_pipelines(every, (), ("vision",))
    assert "image-text-to-text" not in pipes and len(pipes) == 3
    assert (must, never) == ((), ())
    assert narrow_pipelines(pipeline_tags("text"), (), ("vision",))[0] == ("text-generation",)
    assert narrow_pipelines(pipeline_tags("embed"), ("vision",), ())[0] == ()


def test_page_marks_and_cursor_link() -> None:
    from app.llm.hub import cursor_from_link, pack_scan, page_limit, unpack_scan

    assert page_limit(30) == 30
    assert page_limit(1) == 10
    assert page_limit(1000) == 100
    assert page_limit(40) in {30, 50}
    header = '<https://huggingface.co/api/models?limit=10&cursor=abc%2Bdef>; rel="next"'
    assert cursor_from_link(header) == "abc+def"
    assert cursor_from_link(None) is None
    states = [{"hf": "one", "n": 3, "done": False}, {"hf": None, "n": 0, "done": True}]
    packed = pack_scan(states)
    assert packed is not None and packed.startswith("m1.")
    assert unpack_scan(packed, 2) == states
    assert unpack_scan(packed, 3) is None
    assert unpack_scan(None, 2) is None
    assert pack_scan([{"hf": None, "n": 0, "done": True}]) is None


def _fake_hub(
    monkeypatch, feeds: dict[str, list[dict]], page_rows: int = 3, flags: dict | None = None, broken: set | None = None
) -> list:
    """Hub pages per task: `page_rows` rows each, cursors "1", "2", ... like the Link header."""
    from app.runtime.errors import RuntimeApiError

    calls: list = []

    def search_one(pipe, *, search, size, sort, limit, cursor, deadline=None):
        calls.append((pipe, cursor))
        if broken and pipe in broken:
            raise RuntimeApiError("runtime.timeout")
        start = int(cursor or 0) * page_rows
        rows = [
            {**row, "flags": (flags or {}).get(row["id"], (False, False, False, False))}
            for row in feeds.get(pipe, [])[start : start + page_rows]
        ]
        more = start + page_rows < len(feeds.get(pipe, []))
        return rows, (str(int(cursor or 0) + 1) if more else None)

    monkeypatch.setattr("app.llm.hub._search_one", search_one)
    return calls


def _rows(pipe: str, *likes: int) -> list[dict]:
    return [{"id": f"{pipe[:4]}/m{value}", "pipeline_tag": pipe, "likes": value, "downloads": 1} for value in likes]


def test_every_task_merges_by_the_sort_value(monkeypatch) -> None:
    from app.llm.hub import search_hub

    _fake_hub(
        monkeypatch,
        {
            "text-generation": _rows("text-generation", 90, 50, 40, 10),
            "image-text-to-text": _rows("image-text-to-text", 80, 60, 5),
        },
    )
    first = search_hub(search="", pipeline="text,vision", size="any", sort="likes", limit=10)
    assert [item.likes for item in first.items] == [90, 80, 60, 50, 40, 10, 5]
    assert first.has_next is False


def test_next_page_continues_without_gaps_or_repeats(monkeypatch) -> None:
    from app.llm import hub

    monkeypatch.setattr(hub, "page_limit", lambda value: value)
    _fake_hub(
        monkeypatch,
        {
            "text-generation": _rows("text-generation", 90, 50, 40, 10),
            "image-text-to-text": _rows("image-text-to-text", 80, 60, 5),
        },
    )
    seen: list[int] = []
    cursor = None
    for _ in range(5):
        result = hub.search_hub(search="", pipeline="text,vision", size="any", sort="likes", limit=2, cursor=cursor)
        seen.extend(item.likes for item in result.items)
        cursor = result.next_cursor
        if not result.has_next:
            break
    assert seen == [90, 80, 60, 50, 40, 10, 5]


def test_must_and_must_not_filter_while_scanning(monkeypatch) -> None:
    from app.llm.hub import search_hub

    rows = _rows("text-generation", 9, 8, 7, 6, 5, 4)
    flags = {
        "text/m9": (True, True, False, False),
        "text/m8": (True, False, False, False),
        "text/m7": (False, True, False, False),
        "text/m5": (True, False, False, False),
    }
    _fake_hub(monkeypatch, {"text-generation": rows}, flags=flags)
    result = search_hub(
        search="", pipeline="text", size="any", sort="likes", limit=10, capabilities="tools", without="thinking"
    )
    assert [item.id for item in result.items] == ["text/m8", "text/m5"]


def test_flags_come_from_the_listing_and_the_template_is_dropped() -> None:
    from app.llm.hub import _row_hit, slim_row

    row = {
        "id": "a/b-GGUF",
        "pipeline_tag": "text-generation",
        "likes": 3,
        "tags": ["gguf", "reasoning"],
        "gguf": {"architecture": "qwen3moe", "chat_template": "{% if tools %}<tool_call>{% endif %}"},
    }
    row["gguf"].update({"total": 27_009_346_304, "context_length": 131072})
    slim = slim_row(row)
    assert "gguf" not in slim and "tags" not in slim
    hit = _row_hit(slim)
    assert hit is not None and (hit.tools, hit.thinking, hit.vision, hit.moe) == (True, True, False, True)
    assert (hit.parameters, hit.parameter_count, hit.context_length) == ("27B", 27_009_346_304, 131072)


def test_minimum_context_and_installed_repos_filter(monkeypatch) -> None:
    from app.llm import hub

    rows = _rows("text-generation", 9, 8, 7)
    rows[0]["context"] = 131072
    rows[1]["context"] = 32768  # rows[2] has no known context
    _fake_hub(monkeypatch, {"text-generation": rows})
    result = hub.search_hub(search="", pipeline="text", size="any", sort="likes", limit=10, min_context=65536)
    assert [item.id for item in result.items] == ["text/m9"]
    monkeypatch.setattr(hub, "_installed_keys", lambda: {"hf.co/text/m9:q4_k_m", "llama3.2:1b"})
    assert hub.installed_repos() == frozenset({"text/m9"})
    shown = hub.search_hub(search="", pipeline="text", size="any", sort="likes", limit=10, hide_installed=True)
    assert [item.id for item in shown.items] == ["text/m8", "text/m7"]


def test_a_failing_task_is_left_out_and_tried_on_the_next_page(monkeypatch) -> None:
    from app.llm.hub import search_hub, unpack_scan

    calls = _fake_hub(
        monkeypatch,
        {"text-generation": _rows("text-generation", 9, 8), "image-text-to-text": _rows("image-text-to-text", 7)},
        broken={"image-text-to-text"},
    )
    result = search_hub(search="", pipeline="text,vision", size="any", sort="likes", limit=10)
    assert [item.likes for item in result.items] == [9, 8]
    assert result.message_key is None and result.has_next
    states = unpack_scan(result.next_cursor, 2)
    assert states is not None and states[1] == {"hf": None, "n": 0, "done": False}
    assert ("image-text-to-text", None) in calls


def test_rate_limit_stops_calling_the_hub_until_the_window_resets(monkeypatch) -> None:
    import httpx

    from app.llm import hub

    monkeypatch.setitem(hub._COOLDOWN, "until", 0.0)
    monkeypatch.setattr(hub, "_CACHE", {})
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url))
        return httpx.Response(429, headers={"ratelimit": '"api";r=0;t=120'}, json={"error": "rate limited"})

    monkeypatch.setattr(hub, "client", lambda **_: httpx.Client(transport=httpx.MockTransport(handler)))
    first = hub.search_hub(search="", pipeline="text", size="any", sort="likes", limit=10)
    assert first.message_key == "models.hub.rateLimited"
    assert first.retry_after is not None and 100 <= first.retry_after <= 120
    assert len(sent) == 1  # a 429 is not retried
    again = hub.search_hub(search="x", pipeline="all", size="any", sort="likes", limit=10)
    assert again.message_key == "models.hub.rateLimited"
    assert len(sent) == 1  # nothing sent during the cooldown
    files = hub.repo_files("a/b")
    assert files.message_key == "models.hub.rateLimited" and len(sent) == 1


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

    tools, thinking, vision, moe = flags_from_card(
        {
            "pipeline_tag": "text-generation",
            "tags": ["conversational"],
            "gguf": {"chat_template": "use tool_call and <think>"},
        }
    )
    assert (tools, thinking, vision, moe) == (True, True, False, False)
    assert flags_from_card({"pipeline_tag": "image-text-to-text", "gguf": {}})[2] is True
    assert flags_from_card({"gguf": {"architecture": "qwen3moe"}}, "org/plain")[3] is True
    assert flags_from_card({"tags": ["moe"]}, "org/plain")[3] is True
    assert flags_from_card({}, "unsloth/Qwen3-30B-A3B-GGUF")[3] is True
    assert flags_from_card({"gguf": {"architecture": "llama"}}, "TheBloke/Mixtral-8x7B-Instruct-v0.1-GGUF")[3] is True
    assert flags_from_card({}, "unsloth/DeepSeek-V3-GGUF")[3] is True
    assert flags_from_card({"gguf": {"architecture": "qwen2"}}, "bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF")[3] is False
    assert flags_from_card({"gguf": {"architecture": "gemma3"}}, "unsloth/gemma-3-27b-it-GGUF")[3] is False


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
