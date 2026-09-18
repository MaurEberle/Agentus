from __future__ import annotations

from fastapi import APIRouter, Response

from app.settings.models import (
    CredentialCreate,
    CredentialListItem,
    CredentialListResponse,
    CredentialPatch,
)
from app.settings.service import (
    create_credential,
    delete_credential,
    list_credential_items,
    patch_credential,
)

router = APIRouter()


@router.get("/credentials", response_model=CredentialListResponse)
def get_credentials() -> CredentialListResponse:
    return CredentialListResponse(items=list_credential_items())


@router.post("/credentials", response_model=CredentialListItem, status_code=201)
def post_credential(body: CredentialCreate) -> CredentialListItem:
    return create_credential(body)


@router.patch("/credentials/{credential_id}", response_model=CredentialListItem)
def patch_credential_route(
    credential_id: str, body: CredentialPatch
) -> CredentialListItem:
    return patch_credential(credential_id, body)


@router.delete("/credentials/{credential_id}", status_code=204)
def delete_credential_route(credential_id: str) -> Response:
    delete_credential(credential_id)
    return Response(status_code=204)
