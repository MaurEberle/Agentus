from __future__ import annotations

from fastapi import APIRouter

from app.settings.models import AppSettings, AppSettingsPatch
from app.settings.service import load_settings, patch_settings

router = APIRouter()


@router.get("/settings", response_model=AppSettings)
def get_settings() -> AppSettings:
    return load_settings()


@router.patch("/settings", response_model=AppSettings)
def patch_settings_route(body: AppSettingsPatch) -> AppSettings:
    return patch_settings(body)
