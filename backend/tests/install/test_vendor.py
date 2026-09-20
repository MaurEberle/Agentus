from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.http.app import api_version

_REPO = Path(__file__).resolve().parents[3]
_POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_LOCK = _REPO / "installer" / "vendor.lock.json"
_TOML = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_vendor_lock_complete() -> None:
    raw = json.loads(_LOCK.read_text(encoding="utf-8"))
    for key in ("webview2_bootstrapper", "ollama_setup"):
        entry = raw[key]
        assert entry["name"]
        assert entry["url"].startswith("https://")
        assert _HEX64.fullmatch(entry["sha256"]), key
    assert raw["webview2_bootstrapper"]["name"] == "MicrosoftEdgeWebview2Setup.exe"
    assert raw["ollama_setup"]["name"] == "OllamaSetup.exe"


def test_api_version_matches_pyproject() -> None:
    text = _TOML.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match
    assert api_version() == match.group(1)


def test_powershell_scripts_parse() -> None:
    """Windows PowerShell treats $Name: in double quotes as a drive qualifier."""
    scripts = [
        _REPO / "installer" / "fetch-url.ps1",
        _REPO / "scripts" / "build-windows.ps1",
    ]
    for path in scripts:
        assert path.is_file(), path
        cmd = (
            "$e = $null; $t = $null; "
            "[void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{path}', [ref]$t, [ref]$e); "
            "if ($e -and $e.Count) {{ $e | ForEach-Object {{ $_.ToString() }}; exit 1 }}"
        )
        result = subprocess.run(
            [_POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", cmd],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{path}: {result.stdout}{result.stderr}"


def test_nsi_is_per_user_without_portable_marker() -> None:
    nsi = Path(__file__).resolve().parents[3] / "installer" / "Agentus-Network.nsi"
    text = nsi.read_text(encoding="utf-8")
    assert "RequestExecutionLevel user" in text
    assert "AgentusNetwork.exe" in text
    assert r"$LOCALAPPDATA\Programs\Agentus-Network" in text
    assert "portable.txt" not in text
    assert "INSTALL_MODELS" in text
    assert "IfSilent +" not in text
    assert "Start-Process" not in text
    assert "cmd.exe" in text
    assert "--noproxy 127.0.0.1" in text
    assert r"$LOCALAPPDATA\Programs\Ollama\ollama app.exe" in text
    assert 'File "/oname=app.ico"' in text
    assert r'DisplayIcon" "$INSTDIR\app.ico"' in text
    assert r'"$INSTDIR\app.ico" 0' in text
    build = (_REPO / "scripts" / "build-windows.ps1").read_text(encoding="utf-8")
    assert "/INPUTCHARSET" in build
    body = _strcontains_fn(text)
    assert "Push $R2" in body
    assert "Pop $R1" in body
    assert "Exch $R0" in body


def _strcontains_fn(nsi_text: str) -> str:
    start = nsi_text.index("Function StrContains")
    end = nsi_text.index("FunctionEnd", start) + len("FunctionEnd")
    return nsi_text[start:end]


def _makensis() -> Path | None:
    found = shutil.which("makensis")
    if found:
        return Path(found)
    for candidate in (
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "NSIS" / "makensis.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "NSIS" / "makensis.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "NSIS" / "makensis.exe",
        _REPO / "build" / "nsis" / "nsis-3.12" / "makensis.exe",
    ):
        if candidate and candidate.is_file():
            return candidate
    return None


def test_strcontains_oninit_does_not_invalid_opcode(tmp_path: Path) -> None:
    """Empty-stack Exch in StrContains aborted the real setup at .onInit."""
    makensis = _makensis()
    if makensis is None:
        pytest.skip("makensis not found")
    nsi_text = (_REPO / "installer" / "Agentus-Network.nsi").read_text(encoding="utf-8")
    stub = tmp_path / "strcontains.nsi"
    exe = tmp_path / "strcontains-smoke.exe"
    stub.write_text(
        "\n".join(
            [
                "Unicode True",
                f'OutFile "{exe.name}"',
                "RequestExecutionLevel user",
                "SilentInstall silent",
                "Name smoke",
                _strcontains_fn(nsi_text),
                "Function .onInit",
                '  Push "foo INSTALL_MODELS=1 bar"',
                '  Push "INSTALL_MODELS=1"',
                "  Call StrContains",
                "  Pop $1",
                '  StrCmp $1 "1" hit',
                "  Abort",
                "  hit:",
                '  Push "nope"',
                '  Push "INSTALL_MODELS=1"',
                "  Call StrContains",
                "  Pop $1",
                '  StrCmp $1 "0" done',
                "  Abort",
                "  done:",
                "FunctionEnd",
                "Section",
                "SectionEnd",
                "",
            ]
        ),
        encoding="utf-8",
    )
    compiled = subprocess.run(
        [str(makensis), str(stub)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    ran = subprocess.run(
        [str(exe), "/S"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr
