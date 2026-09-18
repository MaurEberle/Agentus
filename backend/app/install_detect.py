"""Read-only detect for WebView2 Runtime and Ollama. NSIS mirrors these rules."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

WEBVIEW2_CLIENT = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
_WEBVIEW2_KEYS = (
    rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT}",
    rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT}",
)


def webview2_present(*, hive_lookup=None) -> bool:
    if hive_lookup is not None:
        return hive_lookup()
    try:
        import winreg
    except ImportError:
        return False
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key in _WEBVIEW2_KEYS:
            try:
                with winreg.OpenKey(hive, key) as handle:
                    pv, _ = winreg.QueryValueEx(handle, "pv")
                if str(pv).strip():
                    return True
            except OSError:
                continue
    return False


def ollama_exe_path() -> Path | None:
    which = shutil.which("ollama") or shutil.which("ollama.exe")
    if which:
        return Path(which)
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    for rel in (Path("Ollama") / "ollama.exe", Path("Programs") / "Ollama" / "ollama.exe"):
        candidate = Path(local) / rel
        if candidate.is_file():
            return candidate
    return None


def ollama_present() -> bool:
    return ollama_exe_path() is not None
