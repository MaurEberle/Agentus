from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("agentus.mcp")

RECIPES_DIR = Path(__file__).resolve().parent / "recipes"


@dataclass
class RecipeRecord:
    id: str
    title_key: str
    transport: str
    runtime: str
    needs_root: bool
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    credential_kinds: list[str] = field(default_factory=list)
    env_from_kind: dict[str, str] = field(default_factory=dict)
    append_root: bool = False
    notes: str | None = None


def _parse(raw: dict[str, Any], filename: str) -> RecipeRecord | None:
    recipe_id = raw.get("id")
    if not isinstance(recipe_id, str) or not recipe_id:
        return None
    if filename != f"{recipe_id}.json":
        log.warning("mcp recipe file %s id mismatch %s", filename, recipe_id)
    transport = raw.get("transport")
    runtime = raw.get("runtime")
    title = raw.get("titleKey")
    needs_root = bool(raw.get("needsRoot", False))
    if transport not in {"stdio", "http"} or not isinstance(runtime, str) or not isinstance(title, str):
        return None
    args = raw.get("args") if isinstance(raw.get("args"), list) else []
    kinds = raw.get("credentialKinds") if isinstance(raw.get("credentialKinds"), list) else []
    env_map = raw.get("envFromKind") if isinstance(raw.get("envFromKind"), dict) else {}
    append = raw.get("appendRoot")
    if append is None:
        append = needs_root
    return RecipeRecord(
        id=recipe_id,
        title_key=title,
        transport=str(transport),
        runtime=runtime,
        needs_root=needs_root,
        command=str(raw["command"]) if raw.get("command") else None,
        args=[str(a) for a in args],
        url=str(raw["url"]) if raw.get("url") else None,
        credential_kinds=[str(k) for k in kinds],
        env_from_kind={str(k): str(v) for k, v in env_map.items()},
        append_root=bool(append),
        notes=str(raw["notes"]) if raw.get("notes") else None,
    )


def load_recipes() -> list[RecipeRecord]:
    if not RECIPES_DIR.is_dir():
        return []
    found: dict[str, RecipeRecord] = {}
    for path in sorted(RECIPES_DIR.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("mcp recipe skip %s: %s", path.name, exc)
            continue
        if not isinstance(raw, dict):
            continue
        parsed = _parse(raw, path.name)
        if parsed is None:
            log.warning("mcp recipe skip %s: invalid fields", path.name)
            continue
        found[parsed.id] = parsed
    return list(found.values())


def get_recipe(recipe_id: str) -> RecipeRecord | None:
    for recipe in load_recipes():
        if recipe.id == recipe_id:
            return recipe
    return None
