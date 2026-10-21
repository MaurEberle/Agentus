"""Prompt library. Files never keep ids. Secret keys are dropped on import."""

from __future__ import annotations

from typing import Any

from app.db.engine import utc_now
from app.db.errors import NotFound
from app.db.prompts import PromptRow, delete_prompts, get_prompt, insert_prompt, list_prompts, update_prompt
from app.http.errors import AppError
from app.networks.transfer import strip_secrets

_MAX_NAME = 200
_MAX_DESCRIPTION = 2000
_MAX_BODY = 100_000
_MAX_TAGS = 32
_MAX_TAG = 48


def _text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _tags(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        tag = " ".join(item.split()).strip()[:_MAX_TAG]
        if not tag or tag.casefold() in seen:
            continue
        seen.add(tag.casefold())
        out.append(tag)
        if len(out) >= _MAX_TAGS:
            break
    return out


def _public(row: PromptRow, *, include_body: bool) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": row.id,
        "name": row.name,
        "description": row.description or "",
        "tags": row.tags,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }
    if include_body:
        item["body"] = row.body
    return item


def _require(prompt_id: str) -> PromptRow:
    row = get_prompt(prompt_id)
    if row is None:
        raise AppError("prompts.notFound", status_code=404)
    return row


def _clean_name(value: object) -> str:
    name = _text(value, _MAX_NAME)
    if not name:
        raise AppError("prompts.nameRequired", status_code=400)
    return name


def list_items() -> list[dict[str, Any]]:
    return [_public(row, include_body=False) for row in list_prompts()]


def get_item(prompt_id: str) -> dict[str, Any]:
    return _public(_require(prompt_id), include_body=True)


def create_item(raw: dict[str, Any]) -> dict[str, Any]:
    row = insert_prompt(
        name=_clean_name(raw.get("name")),
        description=_text(raw.get("description"), _MAX_DESCRIPTION) or None,
        tags=_tags(raw.get("tags")),
        body=_text(raw.get("body"), _MAX_BODY),
    )
    return _public(row, include_body=True)


def patch_item(prompt_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    _require(prompt_id)
    name = _clean_name(raw["name"]) if "name" in raw and raw["name"] is not None else None
    description = _text(raw.get("description"), _MAX_DESCRIPTION) or None if "description" in raw else None
    tags = _tags(raw["tags"]) if "tags" in raw and raw["tags"] is not None else None
    body = _text(raw.get("body"), _MAX_BODY) if "body" in raw and raw["body"] is not None else None
    try:
        row = update_prompt(
            prompt_id,
            name=name,
            description=description,
            tags=tags,
            body=body,
            touch_description="description" in raw,
        )
    except NotFound as exc:
        raise AppError("prompts.notFound", status_code=404) from exc
    return _public(row, include_body=True)


def remove(ids: list[str]) -> None:
    delete_prompts(ids)


def duplicate_item(prompt_id: str) -> dict[str, Any]:
    src = _require(prompt_id)
    row = insert_prompt(
        name=_text(f"{src.name} copy", _MAX_NAME) or "copy",
        description=src.description,
        tags=list(src.tags),
        body=src.body,
    )
    return _public(row, include_body=True)


def _export_row(row: PromptRow) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "agentus.prompt",
        "name": row.name,
        "description": row.description or "",
        "tags": row.tags,
        "body": row.body,
        "exportedAt": utc_now(),
    }


def export_one(prompt_id: str) -> dict[str, Any]:
    return _export_row(_require(prompt_id))


def export_many(ids: list[str]) -> dict[str, Any]:
    items = [_export_row(_require(prompt_id)) for prompt_id in ids]
    return {"exportedAt": utc_now(), "items": items}


def _one_import(raw: object) -> dict[str, Any]:
    cleaned = strip_secrets(raw)
    if not isinstance(cleaned, dict):
        raise AppError("prompts.import.unreadable", status_code=400)
    kind = cleaned.get("kind")
    if kind not in {None, "agentus.prompt"}:
        raise AppError("prompts.import.schema", status_code=400)
    version = cleaned.get("schemaVersion", 1)
    if type(version) is not int or version != 1:
        raise AppError("prompts.import.schema", status_code=400)
    return create_item(
        {
            "name": cleaned.get("name"),
            "description": cleaned.get("description"),
            "tags": cleaned.get("tags"),
            "body": cleaned.get("body"),
        }
    )


def import_items(items: list[object]) -> dict[str, Any]:
    if not items:
        raise AppError("prompts.import.empty", status_code=400)
    saved = [_one_import(item) for item in items]
    return {"items": saved}
