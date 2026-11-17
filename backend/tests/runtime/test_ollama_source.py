from __future__ import annotations

from pathlib import Path

import pytest

from app.runtime import ollama_source
from app.runtime.ollama_source import (
    clean_version,
    find_source,
    is_newer,
    parse_cli_version,
    version_key,
)


def _install(folder: Path) -> Path:
    exe = folder / "ollama.exe"
    (folder / "lib" / "ollama").mkdir(parents=True)
    exe.write_bytes(b"MZ")
    return exe


def test_versions_compare_numerically_and_releases_after_prereleases() -> None:
    assert is_newer("0.40.16", "0.40.9")
    assert is_newer("0.41.0", "0.41.0-rc2")
    assert not is_newer("0.41.0-rc2", "0.41.0")
    assert not is_newer("0.40.16", "0.40.16")
    assert is_newer("0.40.16", None)
    assert not is_newer(None, "0.40.16")
    assert version_key("v0.40.16") == (0, 40, 16, 1, 0)
    assert clean_version("ollama version is 0.40.16") == "0.40.16"


def test_cli_version_reads_the_client_not_a_running_server() -> None:
    both = "ollama version is 0.40.13\nWarning: client version is 0.40.16\n"
    assert parse_cli_version(both) == "0.40.16"
    alone = "Warning: could not connect to a running Ollama instance\nWarning: client version is 0.40.16"
    assert parse_cli_version(alone) == "0.40.16"
    assert parse_cli_version("ollama version is 0.40.16") == "0.40.16"
    assert parse_cli_version("garbage") is None


def test_source_comes_from_the_installer_registry_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "Programs" / "Ollama"
    exe = _install(folder)
    monkeypatch.setattr(ollama_source, "registry_install", lambda: ("0.40.16", folder))
    monkeypatch.setattr(ollama_source, "cli_version", lambda exe: pytest.fail("no CLI call needed"))
    source = find_source()
    assert source is not None
    assert source.exe == exe
    assert source.lib == folder / "lib" / "ollama"
    assert source.version == "0.40.16"


def test_source_without_registry_asks_the_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    exe = _install(tmp_path / "ollama")
    monkeypatch.setattr(ollama_source, "registry_install", lambda: (None, None))
    monkeypatch.setattr(ollama_source, "ollama_exe_path", lambda: exe)
    monkeypatch.setattr(ollama_source, "cli_version", lambda path: "0.40.20")
    source = find_source()
    assert source is not None and source.version == "0.40.20"


def test_source_never_is_agentus_own_copy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    own_root = tmp_path / "runtime" / "ollama"
    exe = _install(own_root / "0.40.16")
    monkeypatch.setattr(ollama_source, "registry_install", lambda: (None, None))
    monkeypatch.setattr(ollama_source, "ollama_exe_path", lambda: exe)
    assert find_source(exclude=own_root) is None


def test_source_without_gpu_libraries_is_not_copied(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    exe = tmp_path / "bin" / "ollama.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(ollama_source, "registry_install", lambda: (None, None))
    monkeypatch.setattr(ollama_source, "ollama_exe_path", lambda: exe)
    assert find_source() is None
