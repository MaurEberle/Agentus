"""Dev Team run, 2026-11-16: Git-Bash paths, git -C, and a fix hint on every failed call."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.tools.file_access_tool import path_candidates
from app.tools.file_access_tool import run as file_access
from app.tools.hints import failure_hint
from app.tools.terminal_tool import _inline_code
from app.tools.terminal_tool import run as terminal

windows_only = pytest.mark.skipif(os.name != "nt", reason="drive letters")


def _posix(path: Path) -> str:
    text = str(path.resolve())
    return "/" + text[0].lower() + text[2:].replace("\\", "/")


@windows_only
def test_git_bash_paths_read_as_windows_paths(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.tsx").write_text("export {}", encoding="utf-8")
    cfg = {"rootPath": str(tmp_path)}
    for path in (_posix(tmp_path / "src" / "App.tsx"), "/src/App.tsx", "src/App.tsx"):
        result = file_access(cfg, {"action": "read", "path": path})
        assert result.ok, path
    assert path_candidates("/mnt/c/dev/x") == ["/mnt/c/dev/x", "C:/dev/x"]


@windows_only
def test_git_bash_path_outside_the_root_stays_refused(tmp_path: Path) -> None:
    (tmp_path / "root").mkdir()
    cfg = {"rootPath": str(tmp_path / "root")}
    outside = _posix(tmp_path / "other.txt")
    result = file_access(cfg, {"action": "write", "path": outside, "content": "x"})
    assert result.error_key == "tools.fileAccess.outsideRoot"
    assert not (tmp_path / "other.txt").exists()
    assert file_access(cfg, {"action": "read", "path": "C:/Windows/win.ini"}).error_key == (
        "tools.fileAccess.outsideRoot"
    )


def test_git_dash_capital_c_is_a_directory_not_inline_code() -> None:
    assert _inline_code("git", ["-C", "sub", "status"]) is False
    assert _inline_code("git", ["-c", "core.pager=cat", "status"]) is True
    assert _inline_code("git", ["--config-env=x=y", "status"]) is True


def test_git_directory_option_stays_inside_the_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    cfg = {"rootPath": str(root), "terminalPrograms": ["git"]}
    outside = terminal(cfg, {"command": f"git -C {tmp_path} status"})
    assert outside.error_key == "tools.terminal.outsideRoot"
    worktree = terminal(cfg, {"command": f"git --work-tree={tmp_path} status"})
    assert worktree.error_key == "tools.terminal.outsideRoot"


def test_hints_name_the_root_actions_and_programs() -> None:
    files = {"rootPath": "C:/dev/app", "fileActions": ["list", "read", "write"]}
    assert "C:/dev/app" in failure_hint("file_access", "tools.fileAccess.outsideRoot", files)
    assert "list, read, write" in failure_hint("file_access", "tools.fileAccess.invalidAction", files)
    term = {"rootPath": "C:/dev/app", "terminalPrograms": ["npm", "git"]}
    assert "git, npm" in failure_hint("terminal", "tools.terminal.notGranted", term)
    assert "no shell" in failure_hint("terminal", "tools.terminal.shellSyntax", term)
    assert "2>&1" in failure_hint("terminal", "tools.terminal.shellSyntax", term)
    inline = failure_hint("terminal", "tools.terminal.inlineCode", term)
    assert "npm run build" in inline and "Do not add helper scripts" in inline
    assert failure_hint("terminal", "tools.terminal.unknown", term) is None
    assert failure_hint("web_search", "tools.webSearch.failed", {}) is None
