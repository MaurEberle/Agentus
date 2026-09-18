from __future__ import annotations

import json
import re
from pathlib import Path

from app.http.app import api_version

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_LOCK = Path(__file__).resolve().parents[3] / "installer" / "vendor.lock.json"
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


def test_nsi_is_per_user_without_portable_marker() -> None:
    nsi = Path(__file__).resolve().parents[3] / "installer" / "Agentus-Network.nsi"
    text = nsi.read_text(encoding="utf-8")
    assert "RequestExecutionLevel user" in text
    assert "AgentusNetwork.exe" in text
    assert r"$LOCALAPPDATA\Programs\Agentus-Network" in text
    assert "portable.txt" not in text
    assert "INSTALL_MODELS" in text
