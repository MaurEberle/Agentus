from __future__ import annotations

from pathlib import Path

from app.db.paths import RAG_DIR_NAME, is_invalid_data_dir
from app.http.errors import AppError

ROOT_RECIPE_IDS = frozenset(
    {"filesystem", "git", "pdf", "excel", "powerpoint", "word", "office"}
)
_STORE_FILES = frozenset(
    {"settings.sqlite", "help.sqlite", "workspace.sqlite", "history.sqlite"}
)
_DSN_SNIPPETS = tuple(name.lower() for name in _STORE_FILES)


def _is_under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def validate_root_path(path: str, *, data_dir: Path, app_home: Path) -> None:
    if not path or not str(path).strip():
        raise AppError("mcp.root.required", status_code=400)
    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, RuntimeError):
        raise AppError("mcp.root.invalid", status_code=400) from None
    if is_invalid_data_dir(resolved):
        raise AppError("mcp.root.invalid", status_code=400)
    home = app_home.expanduser().resolve()
    if resolved == home or _is_under(resolved, home):
        raise AppError("mcp.root.denied", status_code=400)
    if RAG_DIR_NAME in resolved.parts or resolved.name == RAG_DIR_NAME:
        raise AppError("mcp.root.denied", status_code=400)
    data = data_dir.expanduser().resolve()
    if resolved.name in _STORE_FILES:
        raise AppError("mcp.root.denied", status_code=400)
    if resolved.parent == data and resolved.name in _STORE_FILES:
        raise AppError("mcp.root.denied", status_code=400)


def resolve_args(
    args: list[str],
    root_path: str | None,
    *,
    append_root: bool = True,
) -> list[str]:
    placeholder = "{{rootPath}}"
    out = [item.replace(placeholder, root_path or "") for item in args]
    joined = "".join(args)
    if root_path and append_root and placeholder not in joined:
        out.append(root_path)
    return out


def reject_app_db_dsn(secret: str | None) -> None:
    if not secret:
        return
    lowered = secret.lower()
    if any(snippet in lowered for snippet in _DSN_SNIPPETS):
        raise AppError("mcp.postgres.appDb", status_code=400)
