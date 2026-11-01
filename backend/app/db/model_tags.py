"""Local tags for installed Ollama models. The key is ``tag_key``."""

from __future__ import annotations

from app.db.engine import json_dumps, json_loads, locked, transaction
from app.runtime.ollama import tag_key


def _clean(tags: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        text = " ".join(str(raw).split()).strip()[:48]
        if not text:
            continue
        marker = text.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        out.append(text)
        if len(out) >= 24:
            break
    return out


def all_model_tags() -> dict[str, list[str]]:
    with locked("workspace") as conn:
        rows = conn.execute("SELECT model_key, tags FROM model_tags").fetchall()
    found: dict[str, list[str]] = {}
    for row in rows:
        loaded = json_loads(row["tags"], default=[])
        if isinstance(loaded, list):
            found[str(row["model_key"])] = _clean([str(item) for item in loaded])
    return found


def tags_for(name: str) -> list[str]:
    return all_model_tags().get(tag_key(name), [])


def save_model_tags(name: str, tags: list[str]) -> list[str]:
    key = tag_key(name)
    cleaned = _clean(tags)
    with transaction("workspace") as conn:
        if not cleaned:
            conn.execute("DELETE FROM model_tags WHERE model_key = ?", (key,))
        else:
            conn.execute(
                """
                INSERT INTO model_tags (model_key, tags) VALUES (?, ?)
                ON CONFLICT(model_key) DO UPDATE SET tags = excluded.tags
                """,
                (key, json_dumps(cleaned)),
            )
    return cleaned
