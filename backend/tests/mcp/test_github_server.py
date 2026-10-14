from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from app.http.errors import AppError
from app.mcp import github_server as gh

pytestmark = pytest.mark.github_mcp_download


def _zip_with_exe(payload: bytes = b"MZ-official") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("github-mcp-server.exe", payload)
    return buf.getvalue()


def test_ensure_downloads_verifies_and_caches(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(home))
    archive = _zip_with_exe()
    digest = hashlib.sha256(archive).hexdigest()
    monkeypatch.setattr(gh, "ARCHIVE_SHA256", digest)
    fetches: list[str] = []

    def _fetch(url: str) -> bytes:
        fetches.append(url)
        return archive

    monkeypatch.setattr(gh, "_fetch_bytes", _fetch)
    first = gh.ensure_github_mcp_server()
    second = gh.ensure_github_mcp_server()
    dest = gh.installed_exe_path()
    assert first == second == str(dest)
    assert dest.is_file()
    assert dest.read_bytes() == b"MZ-official"
    assert fetches == [gh.DOWNLOAD_URL]


def test_ensure_rejects_bad_hash(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(gh, "ARCHIVE_SHA256", "0" * 64)
    monkeypatch.setattr(gh, "_fetch_bytes", lambda url: _zip_with_exe())
    with pytest.raises(AppError) as exc:
        gh.ensure_github_mcp_server()
    assert exc.value.message_key == "mcp.github.download"
    assert not gh.installed_exe_path().exists()


def test_ensure_rejects_zip_without_exe(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENTUS_NETWORK_HOME", str(tmp_path / "home"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "no exe")
    data = buf.getvalue()
    monkeypatch.setattr(gh, "ARCHIVE_SHA256", hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(gh, "_fetch_bytes", lambda url: data)
    with pytest.raises(AppError) as exc:
        gh.ensure_github_mcp_server()
    assert exc.value.message_key == "mcp.github.download"
