from __future__ import annotations

import sys

from app.mcp.runtime_check import resolve_stdio_command, runtime_available


def test_bundled_uvx_is_used_when_path_has_none(tmp_path, monkeypatch) -> None:
    exe = tmp_path / "uv" / "uvx.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"MZ")
    monkeypatch.setattr("app.mcp.runtime_check.shutil.which", lambda _name: None)
    monkeypatch.setattr("app.mcp.runtime_check.local_app_data", lambda: tmp_path)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "missing" / "AgentusNetwork.exe"))
    assert runtime_available("uvx") is True
    command, args = resolve_stdio_command("uvx", ["mcp-server-git", "--repository"], "uvx")
    assert command == str(exe)
    assert args == ["mcp-server-git", "--repository"]


def test_uvx_missing_is_not_available(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.mcp.runtime_check.shutil.which", lambda _name: None)
    monkeypatch.setattr("app.mcp.runtime_check.local_app_data", lambda: tmp_path)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "missing" / "AgentusNetwork.exe"))
    assert runtime_available("uvx") is False
