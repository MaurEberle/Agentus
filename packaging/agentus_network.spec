# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir for AgentusNetwork.exe. Paths relative to repo root via SPECPATH."""

from __future__ import annotations

import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

spec_root = Path(SPECPATH).resolve()
repo = spec_root.parent
backend = repo / "backend"
frontend_dist = repo / "frontend" / "dist"
help_docs = repo / "resources" / "help_docs"
icon = repo / "resources" / "icons" / "app.ico"

toml = (backend / "pyproject.toml").read_text(encoding="utf-8")
match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', toml)
version = match.group(1) if match else "0.1.0"

datas = [
    (str(frontend_dist), "frontend/dist"),
    (str(help_docs), "help_docs"),
]
recipes = backend / "app" / "mcp" / "recipes"
if recipes.is_dir():
    datas.append((str(recipes), "app/mcp/recipes"))
if icon.is_file():
    datas.append((str(icon), "."))
try:
    datas += copy_metadata("agentus-network")
except Exception:
    pass


def _version_tuple(ver: str) -> tuple:
    nums: list[int] = []
    for part in ver.split("."):
        try:
            nums.append(int(part.split("-")[0]))
        except ValueError:
            nums.append(0)
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


version_info = None
try:
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    vt = _version_tuple(version)
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=vt,
            prodvers=vt,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "Agentus Network"),
                            StringStruct("FileDescription", "Agentus Network"),
                            StringStruct("FileVersion", version),
                            StringStruct("InternalName", "AgentusNetwork"),
                            StringStruct("OriginalFilename", "AgentusNetwork.exe"),
                            StringStruct("ProductName", "Agentus Network"),
                            StringStruct("ProductVersion", version),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )
except Exception:
    version_info = None

binaries: list = []
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan.on",
    "app.host.window",
    "app.main",
    "yaml",
    "multipart",
]
try:
    hiddenimports += collect_submodules("app")
except Exception:
    pass
for pkg in ("webview", "fastapi", "uvicorn", "httpx", "pydantic"):
    try:
        extra_d, extra_b, extra_h = collect_all(pkg)
        datas += extra_d
        binaries += extra_b
        hiddenimports += extra_h
    except Exception:
        pass

a = Analysis(
    [str(backend / "app" / "main.py")],
    pathex=[str(backend)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(spec_root / "rthook_stdio.py")],
    excludes=["pytest", "tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AgentusNetwork",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(icon) if icon.is_file() else None,
    version=version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AgentusNetwork",
)
