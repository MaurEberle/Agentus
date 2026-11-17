from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("agentus.mcp")

RECIPES_DIR = Path(__file__).resolve().parent / "recipes"

# N9: validation looked up the recipe of every MCP node and re-read every file
# each time. Parsed records are kept until a file in the folder changes.
# Callers treat the records as read-only.
_CACHE_LOCK = threading.Lock()
_cache: tuple[tuple, list["RecipeRecord"]] | None = None


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
    root_on_node: bool = False
    listed_tools: list[str] = field(default_factory=list)
    notes: str | None = None
    available: bool = True
    tool_schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    # M12: argument names that hold paths. None = generic list.
    path_keys: list[str] | None = None
    path_check_keys: list[str] = field(default_factory=list)


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
        append = needs_root and not bool(raw.get("rootOnNode", False))
    available = raw.get("available", True)
    if not isinstance(available, bool):
        available = True
    listed = raw.get("listedTools") if isinstance(raw.get("listedTools"), list) else []
    raw_schemas = raw.get("toolSchemas") if isinstance(raw.get("toolSchemas"), dict) else {}
    tool_schemas = {
        str(name): dict(schema)
        for name, schema in raw_schemas.items()
        if isinstance(name, str) and isinstance(schema, dict)
    }
    raw_keys = raw.get("pathKeys")
    path_keys = [str(key) for key in raw_keys if str(key).strip()] if isinstance(raw_keys, list) else None
    raw_check = raw.get("pathCheckKeys")
    path_check = [str(key) for key in raw_check if str(key).strip()] if isinstance(raw_check, list) else []
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
        root_on_node=bool(raw.get("rootOnNode", False)),
        listed_tools=[str(name) for name in listed if str(name).strip()],
        notes=str(raw["notes"]) if raw.get("notes") else None,
        available=available,
        tool_schemas=tool_schemas,
        path_keys=path_keys,
        path_check_keys=path_check,
    )


def _signature(folder: Path) -> tuple:
    items = []
    for path in sorted(folder.glob("*.json")):
        try:
            stat = path.stat()
        except OSError:
            continue
        items.append((path.name, stat.st_mtime_ns, stat.st_size))
    return (str(folder), tuple(items))


def load_recipes() -> list[RecipeRecord]:
    global _cache
    folder = RECIPES_DIR
    if not folder.is_dir():
        return []
    signature = _signature(folder)
    with _CACHE_LOCK:
        if _cache is not None and _cache[0] == signature:
            return list(_cache[1])
    records = _read_recipes(folder)
    with _CACHE_LOCK:
        _cache = (signature, records)
    return list(records)


def _read_recipes(folder: Path) -> list[RecipeRecord]:
    found: dict[str, RecipeRecord] = {}
    for path in sorted(folder.glob("*.json")):
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
