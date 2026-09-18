from __future__ import annotations

import pytest

from app.tools.catalog import reset_mcp_catalog_provider


@pytest.fixture(autouse=True)
def _reset_mcp_hook() -> None:
    reset_mcp_catalog_provider()
    yield
    reset_mcp_catalog_provider()
