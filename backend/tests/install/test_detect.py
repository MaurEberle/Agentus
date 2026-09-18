from __future__ import annotations

import shutil
from pathlib import Path

from app.install_detect import ollama_exe_path, ollama_present, webview2_present


def test_webview2_present_fake_registry() -> None:
    assert webview2_present(hive_lookup=lambda: True) is True


def test_webview2_missing_fake_registry() -> None:
    assert webview2_present(hive_lookup=lambda: False) is False


def test_ollama_present_on_path(monkeypatch, tmp_path: Path) -> None:
    fake = tmp_path / "ollama.exe"
    fake.write_bytes(b"MZ")
    monkeypatch.setattr(
        shutil, "which", lambda name: str(fake) if "ollama" in name.lower() else None
    )
    assert ollama_present() is True
    assert ollama_exe_path() == fake


def test_ollama_present_localappdata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    local = tmp_path / "la"
    exe = local / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    assert ollama_present() is True
    assert ollama_exe_path() == exe


def test_ollama_present_programs_layout(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    local = tmp_path / "la"
    exe = local / "Programs" / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    assert ollama_present() is True
    assert ollama_exe_path() == exe


def test_ollama_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "empty"))
    assert ollama_present() is False
    assert ollama_exe_path() is None
