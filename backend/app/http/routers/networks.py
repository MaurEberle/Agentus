from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from app.http.app import ApiModel
from app.networks import service

router = APIRouter(tags=["networks"])


class IdsBody(ApiModel):
    ids: list[str]


class TagsBody(ApiModel):
    ids: list[str]
    tags: list[str]


class ImportBody(ApiModel):
    document: dict[str, Any]


class PatchBody(ApiModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


@router.get("/networks")
def list_networks() -> dict[str, Any]:
    return {"items": service.list_network_items()}


@router.get("/networks/{network_id}")
def get_network(network_id: str) -> dict[str, Any]:
    return service.get_network_document(network_id)


@router.post("/networks", status_code=201)
def post_network(body: dict[str, Any]) -> dict[str, Any]:
    return service.create_network(body)


@router.put("/networks/{network_id}")
def put_network(network_id: str, body: dict[str, Any]) -> dict[str, Any]:
    return service.replace_network(network_id, body)


@router.patch("/networks/{network_id}")
def patch_network(network_id: str, body: PatchBody) -> dict[str, Any]:
    return service.patch_network(
        network_id,
        body.model_dump(exclude_none=True),
    )


@router.post("/networks/tags")
def post_tags(body: TagsBody) -> dict[str, Any]:
    return {"items": service.add_tags(body.ids, body.tags)}


@router.delete("/networks/{network_id}", status_code=204)
def delete_one(network_id: str) -> Response:
    service.delete_networks([network_id])
    return Response(status_code=204)


@router.delete("/networks", status_code=204)
def delete_many(body: IdsBody) -> Response:
    service.delete_networks(body.ids)
    return Response(status_code=204)


@router.post("/networks/{network_id}/duplicate")
def duplicate(network_id: str) -> dict[str, Any]:
    return service.duplicate(network_id)


@router.post("/networks/{network_id}/validate")
def validate(network_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    document = None
    if body and (body.get("nodes") or body.get("schemaVersion") or body.get("document")):
        document = body.get("document") if "document" in body and "nodes" not in body else body
    return service.validate_network(network_id, document)


@router.get("/networks/{network_id}/export")
def export_network(network_id: str) -> dict[str, Any]:
    return service.export_network(network_id)


@router.post("/networks/import")
def import_network(body: ImportBody) -> dict[str, Any]:
    return service.import_network(body.document)


@router.post("/networks/{network_id}/knowledge/{node_id}/reindex")
def reindex(network_id: str, node_id: str) -> dict[str, str]:
    return service.reindex_knowledge(network_id, node_id)
