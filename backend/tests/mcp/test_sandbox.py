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


def test_confine_relative_and_denied(tmp_path: Path) -> None:
    from app.mcp.sandbox import confine_tool_arguments

    root = tmp_path / "kb"
    root.mkdir()
    inside = confine_tool_arguments({"path": "note.txt"}, str(root))
    assert Path(inside["path"]).resolve() == (root / "note.txt").resolve()
    with pytest.raises(AppError) as err:
        confine_tool_arguments({"fileAbsolutePath": str(tmp_path / "other.xlsx")}, str(root))
    assert err.value.message_key == "mcp.root.denied"


def test_git_keys_leave_revisions_alone(tmp_path: Path) -> None:
    """M12: git uses ``target`` for a revision; only repo_path is a path."""
    from app.mcp.sandbox import confine_tool_arguments

    root = tmp_path / "repo"
    root.mkdir()
    out = confine_tool_arguments(
        {"repo_path": ".", "target": "main", "files": ["src/a.py"]},
        str(root),
        path_keys={"repo_path"},
        check_keys={"files"},
    )
    assert out["target"] == "main"
    assert Path(out["repo_path"]).resolve() == root.resolve()
    assert out["files"] == ["src/a.py"]
    with pytest.raises(AppError) as err:
        confine_tool_arguments(
            {"repo_path": ".", "files": ["../../outside.txt"]},
            str(root),
            path_keys={"repo_path"},
            check_keys={"files"},
        )
    assert err.value.message_key == "mcp.root.denied"


def test_generic_keys_cover_path_lists(tmp_path: Path) -> None:
    from app.mcp.sandbox import confine_tool_arguments

    root = tmp_path / "kb"
    root.mkdir()
    with pytest.raises(AppError):
        confine_tool_arguments({"paths": ["a.txt", str(tmp_path / "x.txt")]}, str(root))
    kept = confine_tool_arguments({"target": "v1.2", "output": "json"}, str(root))
    assert kept == {"target": "v1.2", "output": "json"}


def test_recipes_declare_their_path_keys() -> None:
    from app.mcp.recipe_loader import get_recipe

    git = get_recipe("git")
    excel = get_recipe("excel")
    assert git is not None and git.path_keys == ["repo_path"] and git.path_check_keys == ["files"]
    assert excel is not None and excel.path_keys == ["fileAbsolutePath"]
