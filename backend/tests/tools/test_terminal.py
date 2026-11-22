from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from app.tools.execute import execute_first_party


def _root(tmp_path: Path) -> dict[str, str]:
    return {"rootPath": str(tmp_path), "terminalMode": "restricted", "terminalPrograms": ["python"]}


def test_restricted_runs_allowlisted_program(tmp_path: Path) -> None:
    program = Path(sys.executable).stem
    (tmp_path / "hello.py").write_text("print(41)", encoding="utf-8")
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalMode": "restricted", "terminalPrograms": [program]},
        args={"command": f"{program} hello.py"},
    )
    assert result.ok is True
    assert result.result["exitCode"] == 0
    assert "41" in result.result["stdout"]


def test_restricted_denies_program_outside_allowlist(tmp_path: Path) -> None:
    result = execute_first_party(
        "terminal",
        config=_root(tmp_path),
        args={"command": "cmd /c echo hi"},
    )
    assert result.ok is False
    assert result.error_key == "tools.terminal.notGranted"


def test_restricted_denies_path_and_shell_syntax(tmp_path: Path) -> None:
    path_cmd = execute_first_party(
        "terminal",
        config=_root(tmp_path),
        args={"command": r"C:\Windows\System32\cmd.exe /c echo hi"},
    )
    assert path_cmd.error_key == "tools.terminal.notGranted"
    piped = execute_first_party(
        "terminal",
        config=_root(tmp_path),
        args={"command": 'python -c "print(1)" | more'},
    )
    assert piped.error_key == "tools.terminal.shellSyntax"


def test_missing_and_drive_root_are_rejected(tmp_path: Path) -> None:
    missing = execute_first_party("terminal", args={"command": "python -V"})
    assert missing.error_key == "tools.terminal.missingRoot"
    drive = Path(tmp_path.anchor)
    rooted = execute_first_party(
        "terminal",
        config={"rootPath": str(drive), "terminalPrograms": ["python"]},
        args={"command": "python -V"},
    )
    assert rooted.error_key == "tools.terminal.rootNotDir"


def test_empty_allowlist_denies(tmp_path: Path) -> None:
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalPrograms": []},
        args={"command": "python -V"},
    )
    assert result.error_key == "tools.terminal.notGranted"


def test_output_is_truncated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.terminal_tool.MAX_OUTPUT_CHARS", 8)
    program = Path(sys.executable).stem
    (tmp_path / "long.py").write_text("print('abcdefghij')", encoding="utf-8")
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalPrograms": [program]},
        args={"command": f"{program} long.py"},
    )
    assert result.ok is True
    assert result.result["truncated"] is True
    assert len(result.result["stdout"]) == 8


def test_secret_is_not_injected(tmp_path: Path) -> None:
    program = Path(sys.executable).stem
    (tmp_path / "num.py").write_text("print(123)", encoding="utf-8")
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalPrograms": [program]},
        args={"command": f"{program} num.py"},
        secret="credential-secret-value",
    )
    assert result.ok is True
    blob = f"{result.result['stdout']}{result.result['stderr']}"
    assert "credential-secret-value" not in blob


@pytest.mark.skipif(os.name != "nt", reason="unrestricted mode uses PowerShell")
def test_unrestricted_powershell(tmp_path: Path) -> None:
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalMode": "unrestricted"},
        args={"command": "Write-Output 41"},
    )
    assert result.ok is True
    assert "41" in result.result["stdout"]


@pytest.mark.skipif(os.name != "nt", reason="timeout uses PowerShell")
def test_timeout_kills_the_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.tools.terminal_tool.TIMEOUT_SECONDS", 1)
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalMode": "unrestricted"},
        args={"command": "Start-Sleep -Seconds 30"},
    )
    assert result.ok is False
    assert result.error_key == "tools.terminal.timeout"
    assert result.result["timedOut"] is True


def test_a_timeout_keeps_what_the_command_printed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """On Windows the timeout exception has no output; the agent used to get none."""
    monkeypatch.setattr("app.tools.terminal_tool.TIMEOUT_SECONDS", 2)
    program = Path(sys.executable).stem
    (tmp_path / "slow.py").write_text(
        "import sys, time\nprint('begin', flush=True)\ntime.sleep(30)\n", encoding="utf-8"
    )
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalPrograms": [program]},
        args={"command": f"{program} slow.py"},
    )
    assert result.ok is False and result.error_key == "tools.terminal.timeout"
    assert "begin" in result.result["stdout"]


def test_a_server_runs_briefly_and_returns_what_it_printed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Coder_Team run 2026-11-22: "npm run dev" blocked 200 s; the agent cannot open a browser anyway."""
    monkeypatch.setattr("app.tools.terminal_tool.SERVER_SECONDS", 3)
    program = Path(sys.executable).stem
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalPrograms": [program], "timeoutSec": 300},
        args={"command": f"{program} -u -m http.server 0 --bind 127.0.0.1"},
    )
    assert result.ok is True
    assert result.result["running"] is True and result.result["stoppedAfterSec"] == 3
    assert result.result["exitCode"] is None and result.result["timedOut"] is False
    assert "Serving HTTP" in result.result["stdout"]
    assert "no browser" in result.result["note"]


def test_servers_and_watch_modes_are_recognized(tmp_path: Path) -> None:
    from app.tools.terminal_tool import long_running

    (tmp_path / "package.json").write_text(
        '{"scripts": {"go": "vite --port 3000", "check": "tsc --noEmit", "test": "vitest"}}', encoding="utf-8"
    )
    running = ["npm run dev", "npm start", "npm run go", "npx vite", "vite preview", "yarn dev", "pnpm run preview",
               "npx vitest --watch", "jest --watchAll", "tsc -w", "python -m http.server", "uvicorn app:app"]
    ending = ["npm run build", "npm run check", "npm test", "npm install", "npm i -w pkg", "npx vite build",
              "npx vitest run", "tsc --noEmit", "yarn install", "node server.js", "git status"]
    assert [command for command in running if not long_running(command, tmp_path)] == []
    assert [command for command in ending if long_running(command, tmp_path)] == []


def test_catalog_lists_terminal() -> None:
    from app.tools.catalog import list_catalog_groups, openai_tools_for_kinds

    names = [tool.kind for tool in list_catalog_groups()[0].tools]
    assert "terminal" in names
    described = openai_tools_for_kinds(["terminal"], terminal_programs=["git", "python"])
    assert "git, python" in described[0]["function"]["description"]
    open_shell = openai_tools_for_kinds(["terminal"], terminal_unrestricted=True)
    assert "PowerShell" in open_shell[0]["function"]["description"]


@pytest.mark.parametrize(
    "command",
    [
        'python -c "print(1)"',
        'python -Ic "print(1)"',
        'python -X utf8 -c "print(1)"',
        "git -c alias.x=!calc x",
        "git -C . -c alias.x=!calc x",
        "git --config-env=alias.x=EVIL x",
    ],
)
def test_restricted_blocks_inline_code(tmp_path: Path, command: str) -> None:
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalMode": "restricted", "terminalPrograms": ["python", "git"]},
        args={"command": command},
    )
    assert result.ok is False
    assert result.error_key == "tools.terminal.inlineCode"


def test_inline_check_ignores_subcommand_flags() -> None:
    from app.tools.terminal_tool import _inline_code

    assert _inline_code("git", ["commit", "-c", "HEAD"]) is False
    assert _inline_code("python", ["script.py", "-c"]) is False
    assert _inline_code("python", ["-V"]) is False


def test_default_grant_has_no_interpreter(tmp_path: Path) -> None:
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalMode": "restricted"},
        args={"command": "python -V"},
    )
    assert result.ok is False
    assert result.error_key == "tools.terminal.notGranted"


def test_batch_shim_rejects_cmd_metacharacters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """M14: cmd.exe re-parses the arguments of a .cmd shim, quotes included."""
    shim = tmp_path / "npm.cmd"
    shim.write_text("@echo off\r\necho %*\r\n", encoding="utf-8")
    monkeypatch.setattr("app.tools.terminal_tool.shutil.which", lambda name: str(shim))
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        "app.tools.terminal_tool._spawn",
        lambda root, argv, timeout=None: spawned.append(argv),
    )
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalMode": "restricted", "terminalPrograms": ["npm"]},
        args={"command": 'npm run "x & calc"'},
    )
    assert result.ok is False
    assert result.error_key == "tools.terminal.shellSyntax"
    assert spawned == []


def test_timeout_comes_from_the_node() -> None:
    from app.tools.terminal_tool import _timeout

    assert _timeout({}) == 30
    assert _timeout({"timeoutSec": 120}) == 120
    assert _timeout({"timeoutSec": 1}) == 5
    assert _timeout({"timeoutSec": 9999}) == 600
    assert _timeout({"timeoutSec": "abc"}) == 30


def test_decode_falls_back_to_the_oem_code_page() -> None:
    from app.tools.terminal_tool import _decode

    assert _decode("Größe".encode("utf-8")) == "Größe"
    if os.name == "nt":
        assert _decode("Größe".encode("oem")) == "Größe"


@pytest.mark.skipif(os.name != "nt", reason="unrestricted mode uses PowerShell")
def test_powershell_output_keeps_umlauts(tmp_path: Path) -> None:
    result = execute_first_party(
        "terminal",
        config={"rootPath": str(tmp_path), "terminalMode": "unrestricted"},
        args={"command": "Write-Output ('Gr' + [char]0x00F6 + [char]0x00DF + 'e')"},
    )
    assert result.ok is True
    assert "Größe" in result.result["stdout"]


def _python_root(tmp_path: Path) -> tuple[dict, str]:
    program = Path(sys.executable).stem
    return {"rootPath": str(tmp_path), "terminalMode": "restricted", "terminalPrograms": [program]}, program


def test_harmless_shell_habits_are_taken_off(tmp_path: Path) -> None:
    """Dev Team run, 2026-11-17: 26 of 35 rejected commands were cd to the root, 2>&1 or | head."""
    cfg, program = _python_root(tmp_path)
    (tmp_path / "lines.py").write_text("for i in range(5):\n    print(i)\n", encoding="utf-8")
    result = execute_first_party(
        "terminal",
        config=cfg,
        args={"command": f"cd {tmp_path} && {program} lines.py 2>&1 | head -2"},
    )
    assert result.ok is True, result.error_key
    assert result.result["exitCode"] == 0
    assert result.result["stdout"].split() == ["0", "1"]
    assert result.result["truncated"] is True
    assert result.result["ran"] == f"{program} lines.py"
    assert "2>&1" in result.result["note"] and "| head -2" in result.result["note"]


def test_tail_keeps_the_last_lines(tmp_path: Path) -> None:
    cfg, program = _python_root(tmp_path)
    (tmp_path / "lines.py").write_text("for i in range(5):\n    print(i)\n", encoding="utf-8")
    result = execute_first_party("terminal", config=cfg, args={"command": f"{program} lines.py | tail -n 2"})
    assert result.ok is True, result.error_key
    assert result.result["stdout"].split() == ["3", "4"]


def test_real_shell_syntax_is_still_rejected(tmp_path: Path) -> None:
    cfg, program = _python_root(tmp_path)
    (tmp_path / "sub").mkdir()
    for command in (
        f"cd sub && {program} -V",
        f"{program} -V | more",
        f"{program} -V && {program} -V",
        f"{program} -V > out.txt",
    ):
        result = execute_first_party("terminal", config=cfg, args={"command": command})
        assert result.error_key == "tools.terminal.shellSyntax", command
    assert not (tmp_path / "out.txt").exists()


def test_a_rejected_rest_gets_no_note(tmp_path: Path) -> None:
    """Coder_Team run, 2026-11-20: 'grep … | head -5' lost '| head -5', grep was still not
    granted, and the note said 'Next time send only: grep …'."""
    cfg, program = _python_root(tmp_path)
    for command, key in (
        ("grep -n x style.css | head -5", "tools.terminal.notGranted"),
        (f"{program} -V 2>&1 | more", "tools.terminal.shellSyntax"),
        (f'{program} -c "print(1)" 2>&1', "tools.terminal.inlineCode"),
    ):
        result = execute_first_party("terminal", config=cfg, args={"command": command})
        assert result.error_key == key, command
        payload = result.result or {}
        assert "note" not in payload and "ran" not in payload, command


def test_quoted_text_is_not_touched(tmp_path: Path) -> None:
    from app.tools.terminal_tool import strip_shell_habits

    command = 'git commit -m "fix 2>&1 | head -3"'
    assert strip_shell_habits(command, tmp_path)[0] == command
    assert strip_shell_habits(f'cd "{tmp_path}" && git status', tmp_path)[0] == "git status"
