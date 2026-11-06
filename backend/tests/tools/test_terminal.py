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
