"""The component catalog: node types, fields, ports, rules and error texts.

One file, ``resources/catalog/components.json``, read by the editor (at build time), the
graph validation (ports) and the architect (knowledge). Tests in ``tests/catalog`` keep it
in step with the code.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_ENV = "AGENTUS_NETWORK_CATALOG"
CATALOG_FILE = "components.json"


def catalog_dir() -> Path | None:
    """``resources/catalog`` in a checkout, ``catalog`` next to the frozen app."""
    env = os.environ.get(CATALOG_ENV)
    if env:
        path = Path(env).expanduser()
        return path if path.is_dir() else None
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        base = Path(meipass) if meipass else Path(sys.executable).parent
        path = base / "catalog"
        return path if path.is_dir() else None
    path = Path(__file__).resolve().parents[3] / "resources" / "catalog"
    return path if path.is_dir() else None


@lru_cache(maxsize=1)
def _raw() -> bytes:
    folder = catalog_dir()
    if folder is None or not (folder / CATALOG_FILE).is_file():
        raise RuntimeError("component catalog not found (resources/catalog/components.json)")
    return (folder / CATALOG_FILE).read_bytes()


@lru_cache(maxsize=1)
def load_components() -> dict[str, Any]:
    data = json.loads(_raw().decode("utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("nodeTypes"), list):
        raise RuntimeError("component catalog is malformed")
    return data


def catalog_hash() -> str:
    """Short fingerprint of the catalog; a session notes it to see when the app changed."""
    return hashlib.sha256(_raw()).hexdigest()[:16]


def node_types() -> list[dict[str, Any]]:
    return [item for item in load_components()["nodeTypes"] if isinstance(item, dict)]


def node_spec(node_type: str) -> dict[str, Any] | None:
    return next((item for item in node_types() if item.get("type") == node_type), None)


def tool_kinds() -> list[dict[str, Any]]:
    return [item for item in load_components().get("toolKinds") or [] if isinstance(item, dict)]


def error_texts() -> dict[str, str]:
    raw = load_components().get("errors") or {}
    return {str(key): str(value) for key, value in raw.items()}


def port_handles(direction: str, *, static_only: bool = False) -> dict[str, set[str]]:
    """Allowed handle ids per node type for one direction.

    ``static_only`` leaves out types whose outputs depend on the graph (orchestrator
    channels, router branches); the validation checks those separately.
    """
    out: dict[str, set[str]] = {}
    for spec in node_types():
        if static_only and spec.get("dynamicOut"):
            continue
        ports = spec.get("ports") or []
        out[str(spec["type"])] = {
            str(port["id"]) for port in ports if isinstance(port, dict) and port.get("direction") == direction
        }
    return out
