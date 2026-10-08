from __future__ import annotations

from app.mcp.runtime_check import resolve_stdio_command, runtime_available


def test_none_is_available() -> None:
    assert runtime_available("none") is True


def test_unknown_runtime_false() -> None:
    assert runtime_available("cobol") is False


def test_python_runtime_available() -> None:
    assert runtime_available("python") is True


def test_github_command_resolves_to_official_binary(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "github-mcp-server.exe"
    fake.write_bytes(b"MZ")
    monkeypatch.setattr(
        "app.mcp.github_server.ensure_github_mcp_server",
        lambda: str(fake),
    )
    command, args = resolve_stdio_command("github-mcp-server", [], "none")
    assert command == str(fake)
    assert args == ["stdio"]
    command, args = resolve_stdio_command("github-mcp-server.exe", ["stdio"], "none")
    assert command == str(fake)
    assert args == ["stdio"]
