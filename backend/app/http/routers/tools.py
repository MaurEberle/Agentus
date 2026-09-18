from __future__ import annotations

from fastapi import APIRouter

from app.tools.catalog import list_catalog_groups
from app.tools.models import CatalogResponse

router = APIRouter(tags=["tools"])


@router.get("/tools/catalog", response_model=CatalogResponse)
def get_tools_catalog() -> CatalogResponse:
    return CatalogResponse(groups=list_catalog_groups())
