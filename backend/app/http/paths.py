"""Resolve bundled SPA. One place for frozen vs checkout."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def static_dir() -> Path | None:
    env = os.environ.get("AGENTUS_NETWORK_STATIC_DIR")
    if env:
        path = Path(env).expanduser()
    elif getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        path = Path(meipass) / "frontend" / "dist" if meipass else Path(sys.executable).parent / "frontend" / "dist"
    else:
        path = Path(__file__).resolve().parents[2].parent / "frontend" / "dist"
    try:
        path = path.resolve()
    except OSError:
        return None
    if (path / "index.html").is_file():
        return path
    return None
