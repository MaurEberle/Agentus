"""LocalAppData, portable marker, data-dir guards. No sqlite."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

APP_DIR_NAME = "Agentus-Network"
RAG_DIR_NAME = "agentus_network_rag_documents"
PORTABLE_MARKER = "portable.txt"

_DRIVE_ROOT = re.compile(r"^[A-Za-z]:[\\/]?$")


def local_app_data() -> Path:
    home = os.environ.get("AGENTUS_NETWORK_HOME")
    if home:
        return Path(home).expanduser().resolve()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local).expanduser().resolve() / APP_DIR_NAME
    return Path.home() / "AppData" / "Local" / APP_DIR_NAME


def portable_root() -> Path | None:
    candidates = []
    try:
        candidates.append(Path(sys.executable).resolve().parent)
    except OSError:
        pass
    if sys.argv:
        try:
            candidates.append(Path(sys.argv[0]).resolve().parent)
        except OSError:
            pass
    seen: set[Path] = set()
    for folder in candidates:
        if folder in seen:
            continue
        seen.add(folder)
        if (folder / PORTABLE_MARKER).is_file():
            return folder
    return None


def default_config_path() -> Path:
    portable = portable_root()
    if portable is not None:
        return portable / "config.yaml"
    return local_app_data() / "config.yaml"


def default_data_dir() -> Path:
    portable = portable_root()
    if portable is not None:
        return portable / "data"
    return local_app_data() / "data"


def env_data_dir() -> Path | None:
    raw = os.environ.get("AGENTUS_NETWORK_DATA_DIR")
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def is_invalid_data_dir(path: Path) -> bool:
    """True for filesystem roots (``/``, ``C:\\``) — not a usable data folder."""
    try:
        resolved = path.expanduser().resolve()
    except (OSError, RuntimeError):
        return True
    text = str(resolved).strip()
    if not text:
        return True
    if text in {"/", "\\"}:
        return True
    if _DRIVE_ROOT.fullmatch(text.replace("/", "\\")):
        return True
    if resolved.parent == resolved:
        return True
    if len(resolved.parts) < 2:
        return True
    return False
