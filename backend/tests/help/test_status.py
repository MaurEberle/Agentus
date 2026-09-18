from __future__ import annotations

from app.db import init
from app.help.status import get_status, set_degraded
from app.settings.models import AppSettingsPatch
from app.settings.service import patch_settings


def test_status_unconfigured(api_env) -> None:
    init()
    patch_settings(AppSettingsPatch(help_chat={"provider": "", "model": ""}))
    status = get_status()
    assert status.configured is False


def test_set_degraded(api_env) -> None:
    init()
    set_degraded(True)
    assert get_status().degraded is True
    set_degraded(False)
    assert get_status().degraded is False
