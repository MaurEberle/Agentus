from __future__ import annotations

from fastapi import APIRouter

from app.settings.models import DataLocation, DataLocationPost
from app.settings.service import get_location, post_location

router = APIRouter()


@router.get("/data-location", response_model=DataLocation)
def get_data_location() -> DataLocation:
    return get_location()


@router.post("/data-location", response_model=DataLocation)
def post_data_location(body: DataLocationPost) -> DataLocation:
    return post_location(body)
