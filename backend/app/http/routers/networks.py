from __future__ import annotations

from typing import Any

from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import Field
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


class VersionPatchBody(ApiModel):
    pinned: bool | None = None
    note: str | None = None


class RestoreBody(ApiModel):
    base_revision: int | None = Field(default=None, alias="baseRevision")


class CopyBody(ApiModel):
    name: str | None = None


class RestoreRunBody(ApiModel):
    run_id: str = Field(alias="runId")
    base_revision: int | None = Field(default=None, alias="baseRevision")


@router.put("/networks/{network_id}")
def put_network(
    network_id: str,
    body: dict[str, Any],
    base_revision: Annotated[int | None, Query(alias="baseRevision")] = None,
    new_version: Annotated[bool, Query(alias="newVersion")] = True,
    note: Annotated[str | None, Query(max_length=200)] = None,
) -> dict[str, Any]:
    return service.replace_network(
        network_id, body, base_revision=base_revision, new_version=new_version, note=(note or "").strip() or None
    )


@router.get("/networks/{network_id}/versions")
def get_versions(network_id: str) -> dict[str, Any]:
    return service.network_versions(network_id)


@router.get("/networks/{network_id}/versions/{version}")
def get_version(network_id: str, version: int) -> dict[str, Any]:
    return service.network_version(network_id, version)


@router.patch("/networks/{network_id}/versions/{version}")
def patch_version(network_id: str, version: int, body: VersionPatchBody) -> dict[str, Any]:
    note = body.note.strip()[:200] if body.note is not None else None
    return service.patch_version(network_id, version, pinned=body.pinned, note=note)


@router.delete("/networks/{network_id}/versions/{version}", status_code=204)
def delete_version(network_id: str, version: int) -> Response:
    service.delete_version(network_id, version)
    return Response(status_code=204)


@router.post("/networks/{network_id}/versions/{version}/restore")
def post_restore(network_id: str, version: int, body: RestoreBody) -> dict[str, Any]:
    return service.restore_version(network_id, version, base_revision=body.base_revision)


@router.get("/networks/{network_id}/versions/{version}/diff")
def get_version_diff(network_id: str, version: int) -> dict[str, Any]:
    return service.version_diff(network_id, version)


@router.post("/networks/{network_id}/versions/{version}/copy", status_code=201)
def post_copy_version(network_id: str, version: int, body: CopyBody) -> dict[str, Any]:
    return service.copy_version(network_id, version, body.name)


@router.post("/networks/{network_id}/restore-run")
def post_restore_run(network_id: str, body: RestoreRunBody) -> dict[str, Any]:
    return service.restore_run(network_id, body.run_id, base_revision=body.base_revision)


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


@router.post("/networks/validate")
def validate_unsaved(body: dict[str, Any]) -> dict[str, Any]:
    """M24: "Validate" on a network that was never saved has no id yet."""
    document = body.get("document") if "document" in body and "nodes" not in body else body
    return service.validate_document_body(document)


@router.post("/networks/{network_id}/validate")
def validate(network_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    document = None
    if body and (body.get("nodes") or body.get("schemaVersion") or body.get("document")):
        document = body.get("document") if "document" in body and "nodes" not in body else body
    return service.validate_network(network_id, document)


@router.get("/networks/{network_id}/export")
def export_network(network_id: str) -> dict[str, Any]:
    return service.export_network(network_id)


@router.post("/networks/export")
def export_document(body: dict[str, Any]) -> dict[str, Any]:
    return service.export_document(body)


@router.post("/networks/import", status_code=201)
def import_network(body: ImportBody) -> dict[str, Any]:
    return service.import_network(body.document)


@router.post("/networks/{network_id}/knowledge/{node_id}/reindex")
def reindex(network_id: str, node_id: str) -> dict[str, str]:
    return service.reindex_knowledge(network_id, node_id)
