"""Router rules. First matching branch wins. Default catches the rest."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MATCH_KINDS = ("contains", "startsWith", "firstLine", "regex")
MAX_PATTERN = 200


@dataclass
class RouterRule:
    handle: str
    name: str
    match: str
    pattern: str


@dataclass
class CompiledRouter:
    rules: list[RouterRule] = field(default_factory=list)
    targets: dict[str, str] = field(default_factory=dict)


def branch_rows(data: dict) -> list[dict]:
    raw = data.get("branches")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def branch_pattern(row: dict) -> str:
    pattern = row.get("pattern")
    if isinstance(pattern, str):
        return pattern
    condition = row.get("condition")
    return condition if isinstance(condition, str) else ""


def branch_match(row: dict) -> str:
    kind = row.get("match")
    if isinstance(kind, str) and kind in MATCH_KINDS:
        return kind
    if "match" not in row and (isinstance(row.get("pattern"), str) or isinstance(row.get("condition"), str)):
        return "contains"
    return ""


def rules_from_data(data: dict) -> list[RouterRule]:
    rules: list[RouterRule] = []
    for row in branch_rows(data):
        handle = str(row.get("id") or "").strip()
        if not handle or handle == "default":
            continue
        rules.append(
            RouterRule(
                handle=handle,
                name=str(row.get("name") or "").strip(),
                match=branch_match(row),
                pattern=branch_pattern(row),
            )
        )
    return rules


def rule_matches(match: str, pattern: str, text: str) -> bool:
    if match not in MATCH_KINDS:
        return False
    if match == "regex":
        if not pattern.strip():
            return False
        try:
            return re.search(pattern, text or "") is not None
        except re.error:
            return False
    needle = pattern.strip()
    if not needle:
        return False
    if match == "contains":
        return needle.casefold() in (text or "").casefold()
    if match == "startsWith":
        return (text or "").lstrip().casefold().startswith(needle.casefold())
    line = (text or "").splitlines()[0].strip() if text else ""
    return line.casefold() == needle.casefold()


def pattern_error(match: str, pattern: str) -> str | None:
    if match not in MATCH_KINDS:
        return "graph.router.pattern"
    if match == "regex":
        if not pattern.strip() or len(pattern) > MAX_PATTERN:
            return "graph.router.pattern"
        try:
            re.compile(pattern)
        except re.error:
            return "graph.router.regex"
        return None
    if not pattern.strip() or len(pattern.strip()) > MAX_PATTERN:
        return "graph.router.pattern"
    return None


def resolve_route(router: CompiledRouter, text: str) -> tuple[str | None, str]:
    """Return the target node id and the branch label that won."""
    for rule in router.rules:
        if not rule_matches(rule.match, rule.pattern, text):
            continue
        target = router.targets.get(rule.handle)
        if target:
            return target, rule.name or rule.handle
        fallback = router.targets.get("default")
        return fallback, "default" if fallback else rule.name or rule.handle
    target = router.targets.get("default")
    if target:
        return target, "default"
    return None, "default"
