from __future__ import annotations

from pathlib import Path

import pytest

from app.db.paths import RAG_DIR_NAME
from app.http.errors import AppError
from app.mcp.sandbox import reject_app_db_dsn, validate_root_path


def test_drive_root_invalid(tmp_path: Path) -> None:
    with pytest.raises(AppError) as err:
        validate_root_path(r"C:\\", data_dir=tmp_path, app_home=tmp_path)
    assert err.value.message_key == "mcp.root.invalid"


def test_rag_documents_denied(tmp_path: Path) -> None:
    rag = tmp_path / "data" / RAG_DIR_NAME
    rag.mkdir(parents=True)
    with pytest.raises(AppError) as err:
        validate_root_path(str(rag), data_dir=tmp_path / "data", app_home=tmp_path)
    assert err.value.message_key == "mcp.root.denied"


def test_empty_required(tmp_path: Path) -> None:
    with pytest.raises(AppError) as err:
        validate_root_path("", data_dir=tmp_path, app_home=tmp_path)
    assert err.value.message_key == "mcp.root.required"


def test_postgres_app_db_dsn() -> None:
    with pytest.raises(AppError) as err:
        reject_app_db_dsn("sqlite:///C:/x/workspace.sqlite")
    assert err.value.message_key == "mcp.postgres.appDb"
