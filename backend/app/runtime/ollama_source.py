"""The installed Ollama that Agentus copies its own runtime from.

The official Windows installer (Inno Setup) records version and folder under
a fixed uninstall key. The Ollama tray app keeps that installation current;
Agentus only reads it and never changes it.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app.install_detect import ollama_exe_path

log = logging.getLogger("agentus.runtime.ollama")

OLLAMA_UNINSTALL_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{44E83376-CE68-45EB-8FC1-393500EB558C}_is1"
)

_CREATE_NO_WINDOW = 0x08000000
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-?(rc|beta|alpha|pre)\.?(\d+)?)?", re.IGNORECASE)
# ``ollama --version`` names the server version first and the client (the file
# on disk) second when they differ. Only the client version tells what is installed.
_CLIENT_LINE = re.compile(r"client version is\s+(\S+)", re.IGNORECASE)
_SERVER_LINE = re.compile(r"ollama version is\s+(\S+)", re.IGNORECASE)


@dataclass(frozen=True)
class SourceInstall:
    exe: Path
    lib: Path
    version: str | None


def version_key(text: str | None) -> tuple[int, int, int, int, int] | None:
    """Sortable key. A release sorts after its pre-releases (0.41.0-rc2 < 0.41.0)."""
    if not text:
        return None
    match = _VERSION.search(str(text))
    if match is None:
        return None
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
    if match.group(4):
        return (major, minor, patch, 0, int(match.group(5) or 0))
    return (major, minor, patch, 1, 0)


def clean_version(text: str | None) -> str | None:
    """``0.40.16`` from ``v0.40.16`` or ``ollama version is 0.40.16``."""
    if not text:
        return None
    match = _VERSION.search(str(text))
    return match.group(0) if match else None


def is_newer(candidate: str | None, current: str | None) -> bool:
    new = version_key(candidate)
    old = version_key(current)
    if new is None:
        return False
    if old is None:
        return True
    return new > old


def registry_install() -> tuple[str | None, Path | None]:
    """``(DisplayVersion, InstallLocation)`` of the official installer, if present."""
    if sys.platform != "win32":
        return None, None
    try:
        import winreg
    except ImportError:
        return None, None
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, OLLAMA_UNINSTALL_KEY) as handle:
                version = _reg_value(winreg, handle, "DisplayVersion")
                folder = _reg_value(winreg, handle, "InstallLocation")
        except OSError:
            continue
        path = Path(folder) if folder else None
        return clean_version(version), path
    return None, None


def _reg_value(winreg_module, handle, name: str) -> str | None:
    try:
        value, _kind = winreg_module.QueryValueEx(handle, name)
    except OSError:
        return None
    text = str(value or "").strip()
    return text or None


def parse_cli_version(output: str) -> str | None:
    client = _CLIENT_LINE.search(output or "")
    if client:
        return clean_version(client.group(1))
    server = _SERVER_LINE.search(output or "")
    if server:
        return clean_version(server.group(1))
    return None


def cli_version(exe: Path, *, timeout_sec: float = 10.0) -> str | None:
    """Version of ``exe`` itself. Points OLLAMA_HOST at a dead port, so no server answers."""
    env = dict(os.environ)
    env["OLLAMA_HOST"] = "127.0.0.1:9"
    kwargs: dict = {
        "args": [str(exe), "--version"],
        "stdin": subprocess.DEVNULL,
        "capture_output": True,
        "timeout": timeout_sec,
        "env": env,
        "cwd": str(exe.parent),
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = _CREATE_NO_WINDOW
    try:
        done = subprocess.run(**kwargs)
    except (OSError, subprocess.SubprocessError):
        log.debug("ollama --version failed for %s", exe, exc_info=True)
        return None
    text = (done.stdout or b"").decode("utf-8", "replace") + "\n" + (done.stderr or b"").decode(
        "utf-8", "replace"
    )
    return parse_cli_version(text)


def _inside(path: Path, folder: Path | None) -> bool:
    if folder is None:
        return False
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except (OSError, ValueError):
        return False


def find_source(*, exclude: Path | None = None) -> SourceInstall | None:
    """The installed Ollama, or None. ``exclude`` keeps Agentus' own copy out."""
    reg_version, reg_dir = registry_install()
    exe: Path | None = None
    version: str | None = None
    if reg_dir is not None and (reg_dir / "ollama.exe").is_file():
        exe = reg_dir / "ollama.exe"
        version = reg_version
    if exe is None:
        exe = ollama_exe_path()
    if exe is None or _inside(exe, exclude):
        return None
    lib = exe.parent / "lib" / "ollama"
    if not lib.is_dir():
        # Unknown layout (a package manager or a hand-built binary): copying
        # only ollama.exe would start without GPU libraries.
        return None
    if version is None:
        version = cli_version(exe)
    return SourceInstall(exe=exe, lib=lib, version=version)
