"""Official GitHub MCP server binary (github/github-mcp-server), downloaded on demand."""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.db.paths import local_app_data
from app.http.errors import AppError

log = logging.getLogger("agentus.mcp")

VERSION = "2.0.2"
ARCHIVE = "github-mcp-server_Windows_x86_64.zip"
ARCHIVE_SHA256 = "4ae64087501650752f21c9d5af5378107a5116d94ee1cf37786b22b8c4bd99df"
DOWNLOAD_URL = (
    f"https://github.com/github/github-mcp-server/releases/download/v{VERSION}/{ARCHIVE}"
)
EXE_NAME = "github-mcp-server.exe"
DOWNLOAD_TIMEOUT_SEC = 60
USER_AGENT = "Agentus-Network/1.0"
_MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
_COMMAND_NAMES = frozenset({"github-mcp-server", "github-mcp-server.exe"})

_lock = threading.Lock()


def is_github_mcp_command(command: str | None) -> bool:
    name = Path(command or "").name.lower()
    return name in _COMMAND_NAMES


def installed_exe_path() -> Path:
    return local_app_data() / "mcp" / "github-mcp-server" / VERSION / EXE_NAME


def ensure_github_mcp_server() -> str:
    dest = installed_exe_path()
    if dest.is_file() and dest.stat().st_size > 0:
        return str(dest)
    with _lock:
        if dest.is_file() and dest.stat().st_size > 0:
            return str(dest)
        _install(dest)
        return str(dest)


def _fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SEC) as response:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_ARCHIVE_BYTES:
                raise AppError("mcp.github.download")
            chunks.append(chunk)
        return b"".join(chunks)


def _exe_member(zf: zipfile.ZipFile) -> zipfile.ZipInfo:
    for info in zf.infolist():
        if info.is_dir():
            continue
        path = Path(info.filename)
        if ".." in path.parts:
            continue
        if path.name.lower() == EXE_NAME.lower():
            return info
    raise AppError("mcp.github.download")


def _install(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    archive_path = dest.parent / ARCHIVE
    tmp = dest.with_name(dest.name + ".new")
    try:
        log.info("mcp github download %s", VERSION)
        data = _fetch_bytes(DOWNLOAD_URL)
        digest = hashlib.sha256(data).hexdigest()
        if digest != ARCHIVE_SHA256:
            raise AppError("mcp.github.download")
        archive_path.write_bytes(data)
        with zipfile.ZipFile(archive_path) as zf:
            info = _exe_member(zf)
            with zf.open(info) as src, tmp.open("wb") as out:
                while True:
                    chunk = src.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
        if not tmp.is_file() or tmp.stat().st_size <= 0:
            raise AppError("mcp.github.download")
        os.replace(tmp, dest)
    except AppError:
        raise
    except (OSError, URLError, zipfile.BadZipFile, ValueError) as exc:
        raise AppError("mcp.github.download") from exc
    finally:
        for path in (archive_path, tmp):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
