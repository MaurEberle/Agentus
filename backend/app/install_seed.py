"""Copy bundled help markdown into a new RAG corpus folder once."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from app.db.paths import RAG_DIR_NAME

SEED_MARKER = ".seed-complete"


def bundled_help_docs() -> Path | None:
    env = os.environ.get("AGENTUS_NETWORK_HELP_DOCS")
    if env:
        path = Path(env).expanduser()
        return path if path.is_dir() else None
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        base = Path(meipass) if meipass else Path(sys.executable).parent
        path = base / "help_docs"
        return path if path.is_dir() else None
    # Checkout seed is optional; pytest must stay a no-op without HELP_DOCS.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    path = Path(__file__).resolve().parents[2] / "resources" / "help_docs"
    return path if path.is_dir() else None


def _copy_bundled_files(bundled: Path, target: Path, *, overwrite: bool) -> None:
    for src in bundled.rglob("*"):
        if src.is_symlink() or not src.is_file():
            continue
        rel = src.relative_to(bundled)
        dest = target / rel
        if dest.exists() and not overwrite:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def seed_help_documents(data_dir: Path, *, bundled: Path) -> None:
    target = Path(data_dir) / RAG_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    if not bundled.is_dir():
        return
    if (target / SEED_MARKER).is_file():
        _copy_bundled_files(bundled, target, overwrite=False)
        return
    existing = [
        p
        for p in target.iterdir()
        if p.name != SEED_MARKER and not p.name.startswith(".")
    ]
    if existing:
        return
    _copy_bundled_files(bundled, target, overwrite=True)
    (target / SEED_MARKER).write_text("1\n", encoding="utf-8")
