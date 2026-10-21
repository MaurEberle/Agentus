from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response

from app.http.app import ApiModel
from app.prompts import service

router = APIRouter(tags=["prompts"])


class IdsBody(ApiModel):
    ids: list[str]


class PromptBody(ApiModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    body: str | None = None


class ImportBody(ApiModel):
    items: list[dict[str, Any]]


@router.get("/prompts")
def list_prompts() -> dict[str, Any]:
    return {"items": service.list_items()}


@router.post("/prompts", status_code=201)
def post_prompt(body: PromptBody) -> dict[str, Any]:
    return service.create_item(body.model_dump(exclude_unset=True))


@router.delete("/prompts", status_code=204)
def delete_many(body: IdsBody) -> Response:
    service.remove(body.ids)
    return Response(status_code=204)


@router.post("/prompts/import", status_code=201)
def import_prompts(body: ImportBody) -> dict[str, Any]:
    return service.import_items(body.items)


@router.post("/prompts/export")
def export_many(body: IdsBody) -> dict[str, Any]:
    return service.export_many(body.ids)


@router.get("/prompts/{prompt_id}")
def get_prompt(prompt_id: str) -> dict[str, Any]:
    return service.get_item(prompt_id)


@router.patch("/prompts/{prompt_id}")
def patch_prompt(prompt_id: str, body: PromptBody) -> dict[str, Any]:
    return service.patch_item(prompt_id, body.model_dump(exclude_unset=True))


@router.delete("/prompts/{prompt_id}", status_code=204)
def delete_one(prompt_id: str) -> Response:
    service.remove([prompt_id])
    return Response(status_code=204)


@router.post("/prompts/{prompt_id}/duplicate")
def duplicate(prompt_id: str) -> dict[str, Any]:
    return service.duplicate_item(prompt_id)


@router.get("/prompts/{prompt_id}/export")
def export_one(prompt_id: str) -> dict[str, Any]:
    return service.export_one(prompt_id)
