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
    }
    exe = mapping.get(runtime)
    if not exe:
        return False
    return shutil.which(exe) is not None
