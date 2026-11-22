"""Ranges of number settings on LLM and knowledge nodes.

Validation reports values outside the range before a run starts. Compile and the
agent turn clamp them, so an imported network with a bad value cannot crash a run.

- Temperature: 0 to 2; Anthropic accepts 0 to 1.
- Max tokens: a whole number from 64 to 262144, below the node context.
- Knowledge topK: a whole number from 1 to 20. A negative topK used to cut from the
  end of the hit list and handed the agent almost every snippet.
- Knowledge score threshold: 0 to 1.
"""

from __future__ import annotations

import math

TEMPERATURE_MIN = 0.0
TEMPERATURE_MAX = 2.0
_TEMPERATURE_MAX_BY_PROVIDER = {"anthropic": 1.0}
MAX_TOKENS_MIN = 64
MAX_TOKENS_MAX = 262_144
TOP_K_MIN = 1
TOP_K_MAX = 20
SCORE_MIN = 0.0
SCORE_MAX = 1.0


def number(raw: object) -> float | None:
    """A finite number from a JSON value. Booleans, text and NaN are not numbers."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    value = float(raw)
    return value if math.isfinite(value) else None


def _unset(raw: object) -> bool:
    return raw is None or raw == ""


def temperature_max(provider: str) -> float:
    return _TEMPERATURE_MAX_BY_PROVIDER.get(provider, TEMPERATURE_MAX)


def _whole(value: float) -> bool:
    return value == int(value)


def llm_issues(data: dict) -> list[str]:
    """Validation keys for temperature and maxTokens of one LLM node."""
    issues: list[str] = []
    provider = str(data.get("provider") or "ollama")
    raw = data.get("temperature")
    if not _unset(raw):
        value = number(raw)
        if value is None or not TEMPERATURE_MIN <= value <= temperature_max(provider):
            issues.append("graph.llm.temperature")
    raw = data.get("maxTokens")
    if not _unset(raw):
        value = number(raw)
        if value is None or not _whole(value) or not MAX_TOKENS_MIN <= value <= MAX_TOKENS_MAX:
            issues.append("graph.llm.maxTokens")
        else:
            context = number(data.get("numCtx"))
            if context is not None and context > 0 and value >= context:
                # The output reserve alone would fill the window: no call would fit.
                issues.append("graph.llm.maxTokensContext")
    return issues


def knowledge_issues(data: dict) -> list[str]:
    """Validation keys for topK and scoreThreshold of one knowledge node."""
    issues: list[str] = []
    raw = data.get("topK")
    if not _unset(raw):
        value = number(raw)
        if value is None or not _whole(value) or not TOP_K_MIN <= value <= TOP_K_MAX:
            issues.append("graph.knowledge.topK")
    raw = data.get("scoreThreshold")
    if not _unset(raw):
        value = number(raw)
        if value is None or not SCORE_MIN <= value <= SCORE_MAX:
            issues.append("graph.knowledge.score")
    return issues


def clamped_temperature(data: dict) -> float | None:
    value = number(data.get("temperature"))
    if value is None:
        return None
    provider = str(data.get("provider") or "ollama")
    return min(temperature_max(provider), max(TEMPERATURE_MIN, value))


def clamped_max_tokens(data: dict) -> int | None:
    value = number(data.get("maxTokens"))
    if value is None:
        return None
    return int(min(MAX_TOKENS_MAX, max(MAX_TOKENS_MIN, round(value))))


def knowledge_top_k(data: dict, default: int) -> int:
    value = number(data.get("topK"))
    if value is None or value <= 0:
        return default
    return int(min(TOP_K_MAX, max(TOP_K_MIN, round(value))))


def knowledge_score(data: dict, default: float) -> float:
    value = number(data.get("scoreThreshold"))
    if value is None:
        return default
    return min(SCORE_MAX, max(SCORE_MIN, value))
