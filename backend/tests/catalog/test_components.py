"""The component catalog stays in step with the code (fix/netz-architekt/entwurf.md, 5.3).

A new node field, tool kind, validation rule or limit that is not in
resources/catalog/components.json fails here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

from app.common.components import error_texts, load_components, node_spec, node_types, port_handles, tool_kinds
from app.run import limits, node_values
from app.run.graph_models import NodeType
from app.tools.kinds import FIRST_PARTY_KINDS
from app.tools.terminal_tool import DEFAULT_PROGRAMS
from app.tools.web_search_tool import SEARCH_PROVIDERS

REPO = Path(__file__).resolve().parents[3]
FRONTEND_DOC = REPO / "frontend" / "src" / "modules" / "network" / "model" / "document.ts"
FRONTEND_RANGES = REPO / "frontend" / "src" / "modules" / "network" / "model" / "ranges.ts"
TS_TYPE = {
    "chat_input": "ChatInputData",
    "orchestrator": "OrchestratorNodeData",
    "llm": "LlmNodeData",
    "agent": "AgentNodeData",
    "tool": "ToolNodeData",
    "mcp": "McpNodeData",
    "knowledge": "KnowledgeNodeData",
    "router": "RouterNodeData",
    "end": "EndNodeData",
}


def _ts_source() -> str:
    return FRONTEND_DOC.read_text(encoding="utf-8")


def _ts_keys(type_name: str) -> set[str]:
    match = re.search(rf"export type {type_name} = \{{(.*?)\n\}};", _ts_source(), re.S)
    assert match, type_name
    return set(re.findall(r"^\s+([A-Za-z]+)\??:", match.group(1), re.M))


def _field(node_type: str, key: str) -> dict:
    spec = node_spec(node_type)
    assert spec is not None, node_type
    found = next((item for item in spec["fields"] if item["key"] == key), None)
    assert found is not None, f"{node_type}.{key}"
    return found


def test_node_types_match_backend_and_editor() -> None:
    catalog = {spec["type"] for spec in node_types()}
    assert catalog == set(get_args(NodeType))
    match = re.search(r"export const NODE_TYPES = \[(.*?)\] as const;", _ts_source(), re.S)
    assert match
    assert catalog == set(re.findall(r"'([a-z_]+)'", match.group(1)))


def test_tool_kinds_match_backend_and_editor() -> None:
    kinds = {item["kind"] for item in tool_kinds()}
    assert kinds == set(FIRST_PARTY_KINDS)
    match = re.search(r"export type ToolKind = (.*?);", _ts_source())
    assert match
    assert kinds == set(re.findall(r"'([a-z_]+)'", match.group(1)))
    assert set(_field("tool", "kind")["values"]) == kinds


def test_fields_match_the_editor_types() -> None:
    for spec in node_types():
        catalog = {item["key"] for item in spec["fields"]}
        assert catalog == _ts_keys(TS_TYPE[spec["type"]]), spec["type"]


def test_every_field_is_described() -> None:
    for spec in node_types():
        for item in spec["fields"]:
            assert item.get("description"), f"{spec['type']}.{item['key']}"
            if item["type"] == "enum":
                assert item.get("values"), f"{spec['type']}.{item['key']}"
        for key in ("purpose", "use", "ports", "rules"):
            assert key in spec, f"{spec['type']}.{key}"


def test_tool_fields_name_existing_kinds() -> None:
    kinds = set(FIRST_PARTY_KINDS)
    for item in node_spec("tool")["fields"]:
        assert set(item.get("kinds") or []) <= kinds, item["key"]


def test_every_validation_key_is_explained() -> None:
    sources = ["app/run/validate.py", "app/run/node_values.py", "app/run/router_rules.py"]
    found: set[str] = set()
    for rel in sources:
        found |= set(re.findall(r'"(graph\.[A-Za-z{}_.]+)"', (REPO / "backend" / rel).read_text(encoding="utf-8")))
    roots = set(re.findall(r'_check_tool_root\([^,]+,\s*"([^"]+)"', (REPO / "backend/app/run/validate.py").read_text(encoding="utf-8")))
    assert roots
    keys = set()
    for key in found:
        if "{kind_key}" in key:
            keys |= {key.replace("{kind_key}", root) for root in roots}
        else:
            keys.add(key)
    texts = error_texts()
    assert keys - set(texts) == set()
    assert all(texts[key] for key in keys)


def test_ranges_match_the_backend_limits() -> None:
    expect = {
        ("orchestrator", "agentMissLimit"): (1, limits.MAX_AGENT_MISS_LIMIT, limits.DEFAULT_AGENT_MISS_LIMIT),
        ("orchestrator", "maxToolCalls"): (limits.NODE_TOOL_CALLS_MIN, limits.NODE_TOOL_CALLS_MAX, limits.MAX_ORCHESTRATOR_TOOL_CALLS),
        ("orchestrator", "maxReadCalls"): (limits.NODE_TOOL_CALLS_MIN, limits.NODE_TOOL_CALLS_MAX, limits.MAX_READ_DECISION_CALLS),
        ("orchestrator", "maxLlmCalls"): (limits.NODE_LLM_CALLS_MIN, limits.NODE_LLM_CALLS_MAX, limits.MAX_RUN_LLM_CALLS),
        ("orchestrator", "maxAgentCalls"): (limits.NODE_AGENT_CALLS_MIN, limits.NODE_AGENT_CALLS_MAX, None),
        ("agent", "maxToolCalls"): (limits.NODE_TOOL_CALLS_MIN, limits.NODE_TOOL_CALLS_MAX, limits.MAX_AGENT_TOOL_CALLS),
        ("agent", "reasoningSteps"): (limits.REASONING_STEPS_MIN, limits.REASONING_STEPS_MAX, limits.REASONING_STEPS_DEFAULT),
        ("knowledge", "topK"): (node_values.TOP_K_MIN, node_values.TOP_K_MAX, limits.DEFAULT_TOP_K),
        ("knowledge", "scoreThreshold"): (node_values.SCORE_MIN, node_values.SCORE_MAX, limits.DEFAULT_SCORE_MIN),
        ("llm", "temperature"): (node_values.TEMPERATURE_MIN, node_values.TEMPERATURE_MAX, None),
        ("llm", "maxTokens"): (node_values.MAX_TOKENS_MIN, node_values.MAX_TOKENS_MAX, None),
    }
    for (node_type, key), (low, high, default) in expect.items():
        item = _field(node_type, key)
        assert (item.get("min"), item.get("max")) == (low, high), f"{node_type}.{key}"
        if default is not None:
            assert item.get("default") == default, f"{node_type}.{key} default"


def test_ranges_match_the_editor() -> None:
    ranges = FRONTEND_RANGES.read_text(encoding="utf-8")

    def editor(name: str) -> tuple[float, float]:
        match = re.search(rf"export const {name}: NumberRange = \{{ min: ([\d.]+), max: ([\d.]+)", ranges)
        assert match, name
        return float(match.group(1)), float(match.group(2))

    assert editor("TOP_K_RANGE") == (_field("knowledge", "topK")["min"], _field("knowledge", "topK")["max"])
    assert editor("SCORE_RANGE") == (_field("knowledge", "scoreThreshold")["min"], _field("knowledge", "scoreThreshold")["max"])
    assert editor("SEARCH_RESULTS_RANGE") == (_field("tool", "maxResults")["min"], _field("tool", "maxResults")["max"])
    assert editor("AGENT_MISS_RANGE") == (
        _field("orchestrator", "agentMissLimit")["min"],
        _field("orchestrator", "agentMissLimit")["max"],
    )


def test_tool_values_match_the_tools() -> None:
    assert set(_field("tool", "searchProvider")["values"]) == set(SEARCH_PROVIDERS)
    assert _field("tool", "terminalPrograms")["default"] == list(DEFAULT_PROGRAMS)
    from app.tools.file_access_tool import FILE_ACTION_ORDER

    assert _field("tool", "fileActions")["values"] == list(FILE_ACTION_ORDER)


def test_ports_cover_every_type_and_validation_uses_them() -> None:
    from app.run import validate

    assert set(port_handles("in")) == {spec["type"] for spec in node_types()}
    assert validate._IN_HANDLES == port_handles("in")
    assert validate._OUT_HANDLES == port_handles("out", static_only=True)
    assert "orchestrator" not in validate._OUT_HANDLES and "router" not in validate._OUT_HANDLES


def test_catalog_ships_with_the_app() -> None:
    spec = (REPO / "packaging" / "agentus_network.spec").read_text(encoding="utf-8")
    assert '"resources" / "catalog"' in spec and '(str(catalog), "catalog")' in spec
    assert load_components()["catalogVersion"] >= 1
