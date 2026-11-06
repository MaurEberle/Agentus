"""Real SDK session against a tiny stdio server: no mocks, checks the child really exits."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import psutil
import pytest

from app.mcp.sessions import _SdkSession

_SERVER = """
from mcp.server.mcpserver import MCPServer

app = MCPServer("probe")


@app.tool()
def echo(text: str) -> str:
    return text


app.run()
"""


def _children() -> set[int]:
    return {proc.pid for proc in psutil.Process().children(recursive=True)}


def _running(pid: int) -> bool:
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def _wait_gone(pids: set[int], timeout: float = 5.0) -> set[int]:
    deadline = time.monotonic() + timeout
    alive = set(pids)
    while alive and time.monotonic() < deadline:
        alive = {pid for pid in alive if _running(pid)}
        time.sleep(0.1)
    return alive


@pytest.fixture()
def server_script(tmp_path: Path) -> Path:
    path = tmp_path / "probe_server.py"
    path.write_text(_SERVER, encoding="utf-8")
    return path


def test_list_call_and_close_reaps_child(server_script: Path) -> None:
    before = _children()
    session = _SdkSession(
        transport="stdio",
        command=sys.executable,
        args=[str(server_script)],
        url=None,
        env={},
        cwd=str(server_script.parent),
        headers={},
    )
    spawned = _children() - before
    assert spawned, "server child process should be running"
    try:
        names = [tool.name for tool in session.list_tools()]
        assert "echo" in names
        result = session.call_tool("echo", {"text": "hi"})
        assert "hi" in str(result)
    finally:
        session.close()
    assert _wait_gone(spawned) == set()
    assert not session._thread.is_alive()


def test_failed_start_leaves_no_thread_or_child(tmp_path: Path) -> None:
    broken = tmp_path / "broken.py"
    broken.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    import threading

    before = _children()
    threads_before = set(threading.enumerate())
    with pytest.raises(Exception):
        _SdkSession(
            transport="stdio",
            command=sys.executable,
            args=[str(broken)],
            url=None,
            env={},
            cwd=str(tmp_path),
            headers={},
        )
    assert _wait_gone(_children() - before) == set()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        leaked = [t for t in threading.enumerate() if t not in threads_before and t.is_alive()]
        if not leaked:
            break
        time.sleep(0.1)
    assert leaked == [], f"event-loop thread leaked: {leaked}"
