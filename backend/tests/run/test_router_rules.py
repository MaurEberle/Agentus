from __future__ import annotations

from app.run.graph_models import AgentNetworkDocument
from app.run.router_rules import CompiledRouter, RouterRule, resolve_route
from app.run.validate import validate_document
from tests.run.conftest import mini_doc
from tests.run.test_validate import _orchestrator_doc


def _router(rules: list[RouterRule], targets: dict[str, str]) -> CompiledRouter:
    return CompiledRouter(rules=rules, targets=targets)


def test_contains_is_case_insensitive_and_first_wins() -> None:
    router = _router(
        [
            RouterRule("a", "Wetter", "contains", "regen"),
            RouterRule("b", "Code", "contains", "REGEN"),
        ],
        {"a": "end-a", "b": "end-b", "default": "end-d"},
    )
    assert resolve_route(router, "Viel REGEN heute") == ("end-a", "Wetter")


def test_starts_with_and_first_line() -> None:
    router = _router(
        [
            RouterRule("a", "Start", "startsWith", "hallo"),
            RouterRule("b", "Zeile", "firstLine", "fertig"),
        ],
        {"a": "end-a", "b": "end-b", "default": "end-d"},
    )
    assert resolve_route(router, "  Hallo Welt") == ("end-a", "Start")
    assert resolve_route(router, "Fertig\nmehr") == ("end-b", "Zeile")


def test_regex_is_case_sensitive_and_invalid_does_not_match() -> None:
    router = _router(
        [
            RouterRule("bad", "Kaputt", "regex", "("),
            RouterRule("ok", "Code", "regex", "Bug"),
        ],
        {"bad": "end-bad", "ok": "end-ok", "default": "end-d"},
    )
    assert resolve_route(router, "bug") == ("end-d", "default")
    assert resolve_route(router, "ein Bug") == ("end-ok", "Code")


def test_empty_pattern_never_matches_and_missing_edge_uses_default() -> None:
    router = _router(
        [RouterRule("a", "Leer", "contains", "   ")],
        {"default": "end-d"},
    )
    assert resolve_route(router, "irgendwas") == ("end-d", "default")
    matched = _router(
        [RouterRule("a", "Treffer", "contains", "ja")],
        {"default": "end-d"},
    )
    assert resolve_route(matched, "ja bitte") == ("end-d", "default")


def test_no_default_edge_fails() -> None:
    router = _router([RouterRule("a", "A", "contains", "nein")], {})
    assert resolve_route(router, "ja") == (None, "default")


def _linear_router(**branch: object) -> dict:
    raw = mini_doc()
    raw["nodes"].append(
        {
            "id": "r",
            "type": "router",
            "position": {"x": 0, "y": 0},
            "data": {"branches": [{"id": "a", "name": "A", **branch}]},
        }
    )
    raw["edges"] = [
        edge for edge in raw["edges"] if edge["id"] != "e3"
    ] + [
        {"id": "e3", "source": "ag", "sourceHandle": "message", "target": "r", "targetHandle": "message"},
        {"id": "er", "source": "r", "sourceHandle": "a", "target": "end", "targetHandle": "message"},
        {"id": "ed", "source": "r", "sourceHandle": "default", "target": "end", "targetHandle": "message"},
    ]
    return raw


def test_router_rules_validate() -> None:
    ok = validate_document(
        AgentNetworkDocument.model_validate(_linear_router(match="contains", pattern="ja")),
        data_dir="C:/data",
    )
    assert ok == []
    empty = validate_document(
        AgentNetworkDocument.model_validate(_linear_router(match="contains", pattern="")),
        data_dir="C:/data",
    )
    assert any(item.message_key == "graph.router.pattern" for item in empty)
    broken = validate_document(
        AgentNetworkDocument.model_validate(_linear_router(match="regex", pattern="(")),
        data_dir="C:/data",
    )
    assert any(item.message_key == "graph.router.regex" for item in broken)


def test_legacy_condition_is_a_contains_pattern() -> None:
    raw = _linear_router()
    raw["nodes"][-1]["data"]["branches"] = [{"id": "a", "name": "A", "condition": "ja"}]
    errors = validate_document(AgentNetworkDocument.model_validate(raw), data_dir="C:/data")
    assert errors == []


def test_orchestrator_router_must_end() -> None:
    raw = _orchestrator_doc()
    raw["nodes"].append(
        {
            "id": "r",
            "type": "router",
            "position": {"x": 0, "y": 0},
            "data": {"branches": [{"id": "a", "name": "A", "match": "contains", "pattern": "ja"}]},
        }
    )
    raw["edges"] = [edge for edge in raw["edges"] if edge["id"] != "e5"] + [
        {"id": "e5", "source": "orch", "sourceHandle": "message", "target": "r", "targetHandle": "message"},
        {"id": "er", "source": "r", "sourceHandle": "a", "target": "ag", "targetHandle": "message"},
        {"id": "ed", "source": "r", "sourceHandle": "default", "target": "end", "targetHandle": "message"},
    ]
    errors = validate_document(AgentNetworkDocument.model_validate(raw), data_dir="C:/data")
    assert any(item.message_key == "graph.router.orchestrator" for item in errors)

    for edge in raw["edges"]:
        if edge["id"] == "er":
            edge["target"] = "end"
    fixed = validate_document(AgentNetworkDocument.model_validate(raw), data_dir="C:/data")
    assert fixed == []
