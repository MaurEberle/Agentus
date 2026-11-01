"""Installed models, local tags, delete, Hugging Face search, and Ollama pull."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import Field

from app.common.http import client
from app.db.model_tags import save_model_tags
from app.http.app import ApiModel
from app.llm.catalog import InstalledResponse, list_installed
from app.llm.hub import HubFilesResponse, HubSearchResponse, repo_files, search_hub
from app.llm.pull import pull_lines
from app.llm.usage import model_usages
from app.runtime.errors import raise_for_status
from app.runtime.ollama import resident_index, tag_key, unload
from app.runtime.urls import settings_roots
from app.run.controller import get_controller

router = APIRouter(tags=["models"])


class TagWrite(ApiModel):
    name: str
    tags: list[str] = Field(default_factory=list)


class TagWriteResult(ApiModel):
    name: str
    tags: list[str]


class DeleteBody(ApiModel):
    name: str
    unload: bool = False


class PullBody(ApiModel):
    model: str


def _blocks_for_run(name: str) -> bool:
    status = get_controller().service_status
    if status not in {"starting", "running", "stopping"}:
        return False
    return tag_key(name) in resident_index()


def _delete_upstream(name: str) -> None:
    url = f"{settings_roots()[0]}/api/delete"
    with client(timeout_sec=120.0) as http:
        response = http.request("DELETE", url, json={"model": name})
    if response.status_code == 404:
        return
    raise_for_status(response)


@router.get("/models", response_model=InstalledResponse, response_model_exclude_none=True)
def get_models() -> InstalledResponse:
    return list_installed()


@router.put("/models/tags", response_model=TagWriteResult)
def put_model_tags(body: TagWrite) -> TagWriteResult:
    name = body.name.strip()
    if not name:
        return TagWriteResult(name="", tags=[])
    return TagWriteResult(name=name, tags=save_model_tags(name, body.tags))


@router.post("/models/delete")
def post_delete(body: DeleteBody) -> JSONResponse:
    name = body.name.strip()
    usages = model_usages(name)
    if _blocks_for_run(name):
        usages.append({"kind": "run"})
    loaded = tag_key(name) in resident_index()
    if usages:
        return JSONResponse(
            status_code=409,
            content={"messageKey": "models.inUse", "usages": usages, "loaded": loaded},
        )
    if loaded and not body.unload:
        return JSONResponse(
            status_code=409,
            content={"messageKey": "models.loaded", "usages": [], "loaded": True},
        )
    if loaded:
        unload(name)
    _delete_upstream(name)
    return Response(status_code=204)


@router.get("/models/hub", response_model=HubSearchResponse, response_model_exclude_none=True)
def get_hub(
    search: str = "",
    pipeline: str = "text",
    size: str = "any",
    sort: str = "downloads",
    limit: int = 30,
    cursor: str = "",
    caps: str = "",
) -> HubSearchResponse:
    return search_hub(
        search=search,
        pipeline=pipeline,
        size=size,
        sort=sort,
        limit=limit,
        cursor=cursor or None,
        capabilities=caps,
    )


@router.get("/models/hub/files", response_model=HubFilesResponse, response_model_exclude_none=True)
def get_hub_files(repo_id: Annotated[str, Query(alias="id")]) -> HubFilesResponse:
    return repo_files(repo_id)


@router.post("/models/pull")
def post_pull(body: PullBody) -> StreamingResponse:
    return StreamingResponse(pull_lines(body.model), media_type="application/x-ndjson")
