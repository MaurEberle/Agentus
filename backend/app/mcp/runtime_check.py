from __future__ import annotations

import shutil
import sys
from pathlib import Path

from app.db.paths import local_app_data

_UVX_NAMES = frozenset({"uvx", "uvx.exe"})


def bundled_uvx() -> Path | None:
    """uvx shipped beside the app, or under the Agentus data folder."""
    roots: list[Path] = []
    try:
        roots.append(Path(sys.executable).resolve().parent / "uv")
    except OSError:
        pass
    roots.append(local_app_data() / "uv")
    for root in roots:
        for name in ("uvx.exe", "uvx"):
            candidate = root / name
            if candidate.is_file():
                return candidate
    return None


def uvx_command() -> str | None:
    found = shutil.which("uvx")
    if found:
        return found
    bundled = bundled_uvx()
    return str(bundled) if bundled else None


def runtime_available(runtime: str) -> bool:
    if runtime == "none":
        return True
    if runtime == "uvx":
        return uvx_command() is not None
    mapping = {
        "npx": "npx",
        "node": "node",
        "docker": "docker",
        "python": "python",
    }
    exe = mapping.get(runtime)
    if not exe:
        return False
    if runtime == "python":
        return True
    return shutil.which(exe) is not None


def resolve_stdio_command(
    command: str | None, args: list[str], runtime: str
) -> tuple[str, list[str]]:
    del runtime
    cmd = command or ""
    from app.mcp.github_server import ensure_github_mcp_server, is_github_mcp_command

    if is_github_mcp_command(cmd):
        return ensure_github_mcp_server(), list(args) or ["stdio"]
    if Path(cmd).name.lower() in _UVX_NAMES:
        found = uvx_command()
        return found or cmd, list(args)
    found = shutil.which(cmd) if cmd else None
    return found or cmd, list(args)
