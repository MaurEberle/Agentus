"""Shared folder check and failure result for the first-party tools."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.tools.models import ExecuteResult


def tool_fail(key: str, result: object | None = None) -> ExecuteResult:
    return ExecuteResult(ok=False, error_key=key, result=result)


def is_forbidden_root(path: Path) -> bool:
    try:
        real = path.expanduser().resolve()
    except OSError:
        return True
    _drive, tail = os.path.splitdrive(str(real))
    return len(tail.strip("\\/")) == 0


def configured_root(cfg: dict[str, Any], *, error_prefix: str) -> tuple[Path | None, str | None]:
    root_raw = str(cfg.get("rootPath") or cfg.get("root") or "").strip()
    if not root_raw:
        return None, f"{error_prefix}.missingRoot"
    root_in = Path(root_raw).expanduser()
    if not root_in.is_absolute():
        return None, f"{error_prefix}.rootNotDir"
    try:
        root = root_in.resolve()
    except OSError:
        return None, f"{error_prefix}.rootNotDir"
    if not root.is_dir() or is_forbidden_root(root):
        return None, f"{error_prefix}.rootNotDir"
    return root, None
