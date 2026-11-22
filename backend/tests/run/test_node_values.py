"""Ranges of number settings on LLM and knowledge nodes: validation, clamping, retrieval."""

from __future__ import annotations

import pytest

from app.run.compile import compile_document
from app.run.graph_models import AgentNetworkDocument
from app.run.node_values import (
    clamped_max_tokens,
    clamped_temperature,
    knowledge_issues,
    knowledge_score,
    knowledge_top_k,
    llm_issues,
)
from app.run.validate import validate_document
from tests.run.conftest import mini_doc


@pytest.mark.parametrize("value", [None, "", 0, 0.7, 2, 1.99])
def test_temperature_in_range(value) -> None:
    assert llm_issues({"provider": "openai", "temperature": value}) == []


@pytest.mark.parametrize("value", [-0.1, 2.01, 7, "0.7", True, float("nan")])
def test_temperature_out_of_range(value) -> None:
    assert llm_issues({"provider": "ollama", "temperature": value}) == ["graph.llm.temperature"]


def test_anthropic_allows_temperature_up_to_one() -> None:
    assert llm_issues({"provider": "anthropic", "temperature": 1}) == []
    assert llm_issues({"provider": "anthropic", "temperature": 1.2}) == ["graph.llm.temperature"]


@pytest.mark.parametrize("value", [64, 4096, 262144, 4096.0])
def test_max_tokens_in_range(value) -> None:
    assert llm_issues({"maxTokens": value}) == []


@pytest.mark.parametrize("value", [0, -1, 63, 262145, 100.5, "4096"])
def test_max_tokens_out_of_range(value) -> None:
    assert llm_issues({"maxTokens": value}) == ["graph.llm.maxTokens"]


def test_max_tokens_must_leave_room_in_the_context() -> None:
    assert llm_issues({"maxTokens": 8192, "numCtx": 32768}) == []
    assert llm_issues({"maxTokens": 32768, "numCtx": 32768}) == ["graph.llm.maxTokensContext"]


def test_knowledge_ranges() -> None:
    assert knowledge_issues({"topK": 5, "scoreThreshold": 0}) == []
    assert knowledge_issues({"topK": 20, "scoreThreshold": 1}) == []
    assert knowledge_issues({"topK": 0}) == ["graph.knowledge.topK"]
    assert knowledge_issues({"topK": -3}) == ["graph.knowledge.topK"]
    assert knowledge_issues({"topK": 21}) == ["graph.knowledge.topK"]
    assert knowledge_issues({"topK": 2.5}) == ["graph.knowledge.topK"]
    assert knowledge_issues({"scoreThreshold": 1.5}) == ["graph.knowledge.score"]
    assert knowledge_issues({"scoreThreshold": -0.1}) == ["graph.knowledge.score"]


def test_clamping_keeps_runs_alive() -> None:
    assert clamped_temperature({"temperature": 7}) == 2.0
    assert clamped_temperature({"provider": "anthropic", "temperature": 1.5}) == 1.0
    assert clamped_temperature({"temperature": "hot"}) is None
    assert clamped_max_tokens({"maxTokens": -1}) == 64
    assert clamped_max_tokens({"maxTokens": 10**9}) == 262144
    assert clamped_max_tokens({"maxTokens": 4096.4}) == 4096
    assert knowledge_top_k({"topK": -3}, 4) == 4
    assert knowledge_top_k({"topK": "abc"}, 4) == 4
    assert knowledge_top_k({"topK": 50}, 4) == 20
    assert knowledge_top_k({"topK": 6}, 4) == 6
    assert knowledge_score({"scoreThreshold": 3}, 0.0) == 1.0
    assert knowledge_score({"scoreThreshold": None}, 0.0) == 0.0


def _keys(doc: dict) -> list[str]:
    parsed = AgentNetworkDocument.model_validate(doc)
    return [err.message_key for err in validate_document(parsed, data_dir="C:/agentus-data")]


def _llm(doc: dict) -> dict:
    return next(node for node in doc["nodes"] if node["type"] == "llm")["data"]


def test_validation_reports_the_llm_node() -> None:
    doc = mini_doc(startMessage="go")
    _llm(doc).update({"temperature": 5, "maxTokens": 10})
    parsed = AgentNetworkDocument.model_validate(doc)
    errors = validate_document(parsed, data_dir="C:/agentus-data")
    found = {err.message_key: err.node_id for err in errors}
    llm_id = next(node for node in doc["nodes"] if node["type"] == "llm")["id"]
    assert found.get("graph.llm.temperature") == llm_id
    assert found.get("graph.llm.maxTokens") == llm_id


def test_compile_clamps_imported_values() -> None:
    doc = mini_doc(startMessage="go")
    _llm(doc).update({"temperature": 9, "maxTokens": 5})
    compiled = compile_document(AgentNetworkDocument.model_validate(doc), network_id="n", network_name="n")
    llm = next(iter(compiled.agents.values())).llm
    assert llm.temperature == 2.0
    assert llm.max_tokens == 64
