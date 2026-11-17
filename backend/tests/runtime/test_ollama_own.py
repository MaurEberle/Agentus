from __future__ import annotations

from collections import namedtuple
from pathlib import Path

import pytest

from app.runtime import ollama_own
from app.runtime.ollama_own import (
    MAX_RESTARTS,
    OwnOllama,
    OwnRuntimeError,
    RuntimeState,
    install_copy,
    is_complete,
    lib_entries,
    read_state,
    set_own_for_tests,
    write_state,
)
from app.runtime.ollama_source import SourceInstall

PORT = 45678


def make_source(tmp_path: Path, version: str = "0.40.16") -> SourceInstall:
    folder = tmp_path / f"installed-{version}"
    lib = folder / "lib" / "ollama"
    for name, dll in (
        ("vulkan", "ggml-vulkan.dll"),
        ("cuda_v12", "ggml-cuda.dll"),
        ("cuda_v13", "ggml-cuda.dll"),
        ("rocm_v7_1", "ggml-hip.dll"),
    ):
        (lib / name).mkdir(parents=True, exist_ok=True)
        (lib / name / dll).write_bytes(b"x")
    (lib / "ggml-base.dll").write_bytes(b"b")
    (lib / "llama-server.exe").write_bytes(b"MZ")
    # The fake binary holds its version; the fake probe reads it back.
    (folder / "ollama.exe").write_bytes(version.encode())
    return SourceInstall(exe=folder / "ollama.exe", lib=lib, version=version)


class FakeProc:
    def __init__(self, folder: str) -> None:
        self.folder = folder
        self.returncode: int | None = None
        self.pid = 4242

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int | None:
        return self.returncode


class FakeJob:
    active = False

    def terminate(self) -> None:
        return None


class Harness:
    def __init__(self, tmp_path: Path, source: SourceInstall | None) -> None:
        self.source = source
        self.spawned: list[str] = []
        self.procs: list[FakeProc] = []
        self.reports: dict[str, str | None] = {}
        self.fallbacks = 0
        self.root = tmp_path / "runtime" / "ollama"
        self.own = OwnOllama(
            self.root,
            find=lambda: self.source,
            spawn=self._spawn,
            ready=self._ready,
            probe=lambda exe: exe.read_bytes().decode(),
            kind=lambda lib: "vulkan",
            fallback=self._fallback,
            port=lambda: PORT,
        )

    def _spawn(self, exe: Path, port: int, log_path: Path | None) -> tuple[FakeProc, FakeJob]:
        assert port == PORT
        self.spawned.append(exe.parent.name)
        proc = FakeProc(exe.parent.name)
        self.procs.append(proc)
        return proc, FakeJob()

    def _ready(self, proc: FakeProc, port: int, timeout: float) -> str | None:
        return self.reports.get(proc.folder, proc.folder)

    def _fallback(self) -> None:
        self.fallbacks += 1

    def boot(self) -> OwnOllama:
        self.own.begin("own")
        self.own.boot()
        return self.own


@pytest.fixture(autouse=True)
def _no_instance():
    set_own_for_tests(None)
    yield
    set_own_for_tests(None)


def _names(entries: list[Path]) -> list[str]:
    return sorted(entry.name for entry in entries)


def test_copy_takes_only_the_pinned_gpu_backend(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    no_drivers = tmp_path / "system32"
    no_drivers.mkdir()
    base = ["ggml-base.dll", "llama-server.exe"]
    assert _names(lib_entries(source.lib, "vulkan", system32=no_drivers)) == base + ["vulkan"]
    assert _names(lib_entries(source.lib, "cuda", system32=no_drivers)) == ["cuda_v13"] + base
    assert _names(lib_entries(source.lib, "hip", system32=no_drivers)) == base + ["rocm_v7_1"]


def test_copy_without_a_pin_follows_the_installed_drivers(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    system32 = tmp_path / "system32"
    system32.mkdir()
    (system32 / "nvcuda.dll").write_bytes(b"")
    assert _names(lib_entries(source.lib, None, system32=system32)) == [
        "cuda_v12",
        "cuda_v13",
        "ggml-base.dll",
        "llama-server.exe",
        "vulkan",
    ]


def test_install_copy_stages_and_marks_the_folder_complete(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    root = tmp_path / "runtime"
    assert install_copy(source, root, kind="vulkan") == "0.40.16"
    target = root / "0.40.16"
    assert is_complete(target)
    assert (target / "lib" / "ollama" / "vulkan" / "ggml-vulkan.dll").is_file()
    assert (target / "lib" / "ollama" / "llama-server.exe").is_file()
    assert not (target / "lib" / "ollama" / "cuda_v13").exists()
    assert [child.name for child in root.iterdir()] == ["0.40.16"]


def test_copy_made_while_the_installer_runs_is_dropped(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    root = tmp_path / "runtime"
    with pytest.raises(OwnRuntimeError) as caught:
        install_copy(source, root, kind="vulkan", recheck=lambda: "0.40.17")
    assert caught.value.key == "runtime.own.sourceChanged"
    assert list(root.iterdir()) == []


def test_copy_that_does_not_start_is_dropped(tmp_path: Path) -> None:
    source = make_source(tmp_path)
    root = tmp_path / "runtime"
    with pytest.raises(OwnRuntimeError) as caught:
        install_copy(source, root, kind="vulkan", probe=lambda exe: None)
    assert caught.value.key == "runtime.own.probeFailed"
    assert list(root.iterdir()) == []


def test_copy_needs_free_disk_space(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(ollama_own.shutil, "disk_usage", lambda path: usage(1, 1, 0))
    with pytest.raises(OwnRuntimeError) as caught:
        install_copy(make_source(tmp_path), tmp_path / "runtime", kind="vulkan")
    assert caught.value.key == "runtime.own.diskFull"


def test_first_boot_copies_the_installed_ollama_and_starts_it(tmp_path: Path) -> None:
    harness = Harness(tmp_path, make_source(tmp_path))
    harness.own.begin("own")
    assert harness.own.root_url() == f"http://127.0.0.1:{PORT}"
    assert harness.own.wait_ready(0.01) is False
    own = harness.own
    own.boot()
    assert own.state == "running"
    assert own.version == "0.40.16"
    assert own.wait_ready(0.01) is True
    assert own.lib_dir() == harness.root / "0.40.16" / "lib" / "ollama"
    assert read_state(harness.root).current == "0.40.16"
    assert harness.spawned == ["0.40.16"]
    assert harness.fallbacks == 0
    own.shutdown()
    assert own.state == "stopped"
    assert own.root_url() is None
    assert harness.procs[0].returncode == -9


def test_without_installed_ollama_the_configured_address_is_used(tmp_path: Path) -> None:
    harness = Harness(tmp_path, None)
    own = harness.boot()
    assert own.state == "unavailable"
    assert own.message_key == "runtime.own.noSource"
    assert own.root_url() is None
    assert own.wait_ready(0.01) is True
    assert harness.fallbacks == 1


def test_a_new_version_that_does_not_start_rolls_back(tmp_path: Path) -> None:
    harness = Harness(tmp_path, make_source(tmp_path, "0.40.17"))
    install_copy(make_source(tmp_path, "0.40.16"), harness.root, kind="vulkan")
    install_copy(make_source(tmp_path, "0.40.17"), harness.root, kind="vulkan")
    write_state(harness.root, RuntimeState(current="0.40.17", previous="0.40.16", pending=True))
    harness.reports["0.40.17"] = None
    own = harness.boot()
    assert harness.spawned == ["0.40.17", "0.40.16"]
    assert own.state == "running"
    assert own.version == "0.40.16"
    assert own.message_key == "runtime.own.rolledBack"
    assert own.message_params == {"failed": "0.40.17", "version": "0.40.16"}
    state = read_state(harness.root)
    assert (state.current, state.previous, state.failed) == ("0.40.16", None, "0.40.17")
    # The version that failed is not offered again.
    assert own.check_update() is None


def test_a_good_start_confirms_the_update_and_prunes_old_copies(tmp_path: Path) -> None:
    harness = Harness(tmp_path, make_source(tmp_path, "0.40.16"))
    for version in ("0.40.10", "0.40.13", "0.40.16"):
        install_copy(make_source(tmp_path, version), harness.root, kind="vulkan")
    (harness.root / ".staging-dead").mkdir()
    write_state(harness.root, RuntimeState(current="0.40.16", previous="0.40.13", pending=True))
    harness.boot()
    state = read_state(harness.root)
    assert (state.current, state.previous, state.pending) == ("0.40.16", "0.40.13", False)
    assert sorted(child.name for child in harness.root.iterdir() if child.is_dir()) == ["0.40.13", "0.40.16"]


def test_a_newer_installed_version_is_offered(tmp_path: Path) -> None:
    harness = Harness(tmp_path, make_source(tmp_path, "0.40.16"))
    own = harness.boot()
    assert own.check_update() is None
    harness.source = make_source(tmp_path, "0.40.17")
    assert own.check_update() == "0.40.17"
    snap = own.snapshot()
    assert snap["installed_version"] == "0.40.17"
    assert snap["update_version"] == "0.40.17"
    assert snap["checked_at"]


@pytest.mark.parametrize(
    ("run_busy", "download_running", "key"),
    [(True, False, "runtime.own.busy"), (False, True, "runtime.own.downloadRunning")],
)
def test_update_waits_for_runs_and_downloads(tmp_path: Path, run_busy: bool, download_running: bool, key: str) -> None:
    harness = Harness(tmp_path, make_source(tmp_path, "0.40.16"))
    own = harness.boot()
    harness.source = make_source(tmp_path, "0.40.17")
    with pytest.raises(OwnRuntimeError) as caught:
        own.apply_update(run_busy=run_busy, download_running=download_running)
    assert caught.value.key == key
    assert read_state(harness.root).current == "0.40.16"


def test_update_without_a_newer_version_is_refused(tmp_path: Path) -> None:
    own = Harness(tmp_path, make_source(tmp_path, "0.40.16")).boot()
    with pytest.raises(OwnRuntimeError) as caught:
        own.apply_update(run_busy=False, download_running=False)
    assert caught.value.key == "runtime.own.noUpdate"


def test_update_stages_the_new_version_for_the_next_start(tmp_path: Path) -> None:
    harness = Harness(tmp_path, make_source(tmp_path, "0.40.16"))
    own = harness.boot()
    harness.source = make_source(tmp_path, "0.40.17")
    own.check_update()
    assert own.apply_update(run_busy=False, download_running=False) == "0.40.17"
    state = read_state(harness.root)
    assert (state.current, state.previous, state.pending) == ("0.40.17", "0.40.16", True)
    assert is_complete(harness.root / "0.40.17")
    snap = own.snapshot()
    assert snap["staged_version"] == "0.40.17"
    assert snap["update_version"] is None
    # The running copy stays until the restart.
    assert harness.spawned == ["0.40.16"]
    assert own.version == "0.40.16"


def test_a_crashed_daemon_is_restarted_then_given_up(tmp_path: Path) -> None:
    harness = Harness(tmp_path, make_source(tmp_path))
    own = harness.boot()
    for attempt in range(MAX_RESTARTS):
        harness.procs[-1].returncode = 1
        own.supervise_once()
        assert own.state == "running"
        assert len(harness.spawned) == attempt + 2
    harness.procs[-1].returncode = 1
    own.supervise_once()
    assert own.state == "failed"
    assert own.message_key == "runtime.own.crashed"
    assert own.root_url() is None
    assert harness.fallbacks == 1


def test_requests_go_to_the_own_copy_while_it_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.runtime.ollama_embed_runner import llama_server_exe
    from app.runtime.ollama_gen import ollama_server_log
    from app.runtime.urls import settings_roots
    from app.settings.defaults import default_settings

    monkeypatch.setattr("app.settings.service.load_settings", default_settings)
    log_path = tmp_path / "logs" / "ollama-server.log"
    harness = Harness(tmp_path, make_source(tmp_path))
    harness.own.log_path = log_path
    own = harness.boot()
    set_own_for_tests(own)
    log_path.parent.mkdir(parents=True)
    log_path.write_text("", encoding="utf-8")
    assert settings_roots()[0] == f"http://127.0.0.1:{PORT}"
    assert ollama_server_log() == log_path
    assert llama_server_exe() == harness.root / "0.40.16" / "lib" / "ollama" / "llama-server.exe"
    own.shutdown()
    assert settings_roots()[0] == "http://127.0.0.1:11434"


def test_external_mode_keeps_the_configured_address(tmp_path: Path) -> None:
    harness = Harness(tmp_path, make_source(tmp_path))
    harness.own.begin("external")
    assert harness.own.state == "disabled"
    assert harness.own.root_url() is None
    assert harness.own.wait_ready(0.01) is True
    assert harness.spawned == []
