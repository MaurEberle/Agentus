from __future__ import annotations

import shutil


def runtime_available(runtime: str) -> bool:
    if runtime == "none":
        return True
    mapping = {
        "npx": "npx",
        "node": "node",
        "docker": "docker",
        "uvx": "uvx",
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
    found = shutil.which(cmd) if cmd else None
    return found or cmd, list(args)
