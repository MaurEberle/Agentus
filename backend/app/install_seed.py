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


def seed_help_documents(data_dir: Path, *, bundled: Path) -> None:
    target = Path(data_dir) / RAG_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    if (target / SEED_MARKER).is_file():
        return
    existing = [
        p
        for p in target.iterdir()
        if p.name != SEED_MARKER and not p.name.startswith(".")
    ]
    if existing:
        return
    if not bundled.is_dir():
        return
    for src in bundled.rglob("*"):
        if src.is_symlink() or not src.is_file():
            continue
        rel = src.relative_to(bundled)
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    (target / SEED_MARKER).write_text("1\n", encoding="utf-8")
