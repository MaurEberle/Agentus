"""Agentus' own Ollama: a private copy of the installed Ollama, run by Agentus.

The Ollama tray app updates itself every hour. Its installer stops the server
and replaces the files, and Agentus lost Ollama for one to two minutes (seen on
2026-11-16 from 21:53 to 21:55, including the embedding runner). Agentus now
copies ``ollama.exe`` and the GPU libraries it needs into its own folder,
starts that copy on its own port with the same model folder, and ends it when
Agentus ends. An update of the installed Ollama does not touch the copy. Agentus
offers the newer version and takes it over on request; the app then restarts.

Folder (``%LOCALAPPDATA%\\Agentus-Network\\runtime\\ollama``)::

    state.json       current, previous, pending, failed
    0.40.16\\        ollama.exe, lib\\ollama\\..., .agentus-complete
    0.40.13\\        the version before, kept for a rollback
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import Field

from app.common.http import client
from app.common.winjob import KillOnCloseJob
from app.http.app import ApiModel
from app.runtime.ollama_source import SourceInstall, clean_version, find_source, is_newer

log = logging.getLogger("agentus.runtime.ollama")

Mode = Literal["own", "external"]
State = Literal["disabled", "preparing", "starting", "running", "failed", "unavailable", "stopped"]

DEFAULT_PORT = 11435
START_TIMEOUT_SEC = 45.0
PROBE_TIMEOUT_SEC = 30.0
CHECK_INTERVAL_SEC = 3600.0
SUPERVISE_SEC = 5.0
MAX_RESTARTS = 3
RESTART_WINDOW_SEC = 600.0
DISK_MARGIN_BYTES = 256 * 1024 * 1024
LOG_MAX_BYTES = 20 * 1024 * 1024
STATE_FILE = "state.json"
COMPLETE_MARKER = ".agentus-complete"
LOG_NAME = "ollama-server.log"

_CREATE_NO_WINDOW = 0x08000000
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_ACTIVE: tuple[str, ...] = ("preparing", "starting", "running")


class OwnRuntimeError(Exception):
    def __init__(self, key: str, *, status_code: int = 409) -> None:
        super().__init__(key)
        self.key = key
        self.status_code = status_code


class OwnOllamaStatus(ApiModel):
    mode: Mode
    configured_mode: Mode
    restart_required: bool = False
    state: State
    version: str | None = None
    port: int | None = None
    base_url: str | None = None
    installed_version: str | None = None
    update_version: str | None = None
    staged_version: str | None = None
    checked_at: str | None = None
    message_key: str | None = None
    message_params: dict[str, str] = Field(default_factory=dict)
    can_restart: bool = False
    run_busy: bool = False
    download_running: bool = False
    log_path: str | None = None


# --- folder and state -------------------------------------------------------


@dataclass
class RuntimeState:
    current: str | None = None
    previous: str | None = None
    pending: bool = False
    failed: str | None = None


def runtime_root() -> Path:
    from app.db.paths import local_app_data

    return local_app_data() / "runtime" / "ollama"


def server_log_path() -> Path:
    from app.db.paths import local_app_data

    return local_app_data() / "logs" / LOG_NAME


def read_state(root: Path) -> RuntimeState:
    try:
        raw = json.loads((root / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return RuntimeState()
    if not isinstance(raw, dict):
        return RuntimeState()

    def text(key: str) -> str | None:
        value = raw.get(key)
        return clean_version(value) if isinstance(value, str) else None

    return RuntimeState(
        current=text("current"),
        previous=text("previous"),
        pending=bool(raw.get("pending")),
        failed=text("failed"),
    )


def write_state(root: Path, state: RuntimeState) -> None:
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f"{STATE_FILE}.tmp"
    tmp.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
    os.replace(tmp, root / STATE_FILE)


def is_complete(folder: Path | None) -> bool:
    return (
        folder is not None
        and (folder / "ollama.exe").is_file()
        and (folder / COMPLETE_MARKER).is_file()
    )


def prune_versions(root: Path, keep: set[str | None]) -> None:
    """Remove copies other than ``keep`` and leftovers of an interrupted copy."""
    if not root.is_dir():
        return
    names = {name for name in keep if name}
    for child in root.iterdir():
        if not child.is_dir() or child.name in names:
            continue
        shutil.rmtree(child, ignore_errors=True)


# --- copying ----------------------------------------------------------------


def backend_kind(lib: Path) -> str | None:
    """The GPU backend Agentus pins for this machine (same rule as the daemon env)."""
    from app.runtime.ollama_daemon import inference_vendor_id
    from app.runtime.ollama_embed_runner import backend_kind_for_vendor

    return backend_kind_for_vendor(lib, inference_vendor_id())


def lib_entries(lib: Path, kind: str | None, *, system32: Path | None = None) -> list[Path]:
    """What of ``lib/ollama`` the copy needs.

    Everything except GPU folders this machine cannot use. With a pinned backend
    (NVIDIA, AMD) only that folder goes along; the daemon env points Ollama at
    it. Without a pin, Ollama discovers on its own: CUDA and ROCm only with
    their driver, Vulkan always. All CUDA, ROCm and Vulkan folders together are
    over 3 GB; one of them is 40 MB to 1.2 GB.
    """
    from app.runtime.ollama_embed_runner import _system32, preferred_gpu_dir

    chosen = preferred_gpu_dir(lib, vendor=kind) if kind else None
    sys32 = system32 or _system32()
    has_cuda = (sys32 / "nvcuda.dll").is_file()
    has_hip = bool(list(sys32.glob("amdhip64*.dll")))
    out: list[Path] = []
    for child in sorted(lib.iterdir(), key=lambda path: path.name.lower()):
        if child.is_dir():
            name = child.name.lower()
            cuda = name.startswith("cuda")
            rocm = name.startswith("rocm")
            if cuda or rocm or name == "vulkan":
                if kind is not None:
                    if chosen is None or child.name != chosen.name:
                        continue
                elif (cuda and not has_cuda) or (rocm and not has_hip):
                    continue
        out.append(child)
    return out


def _tree_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def install_copy(
    source: SourceInstall,
    root: Path,
    *,
    kind: str | None,
    probe: Callable[[Path], str | None] | None = None,
    recheck: Callable[[], str | None] | None = None,
) -> str:
    """Copy the installed Ollama into ``root/<version>``. Returns the version.

    The copy goes to a staging folder first and is renamed only when complete,
    so an interrupted copy never becomes the current version. ``probe`` starts
    the staged copy once (on a free port) and returns the version it reports;
    ``recheck`` reads the installed version again after copying, so a copy made
    while the Ollama installer was replacing files is thrown away.
    """
    version = clean_version(source.version)
    if version is not None and is_complete(root / version):
        return version
    if version is None and probe is None:
        raise OwnRuntimeError("runtime.own.versionUnknown")
    try:
        entries = lib_entries(source.lib, kind)
        needed = source.exe.stat().st_size + sum(_tree_size(entry) for entry in entries)
        root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(root).free < needed + DISK_MARGIN_BYTES:
            raise OwnRuntimeError("runtime.own.diskFull")
    except OSError as exc:
        log.exception("could not read the installed Ollama at %s", source.exe.parent)
        raise OwnRuntimeError("runtime.own.copyFailed") from exc
    staging = root / f".staging-{uuid.uuid4().hex[:8]}"
    try:
        lib_target = staging / "lib" / "ollama"
        lib_target.mkdir(parents=True)
        shutil.copy2(source.exe, staging / "ollama.exe")
        for entry in entries:
            if entry.is_dir():
                shutil.copytree(entry, lib_target / entry.name)
            else:
                shutil.copy2(entry, lib_target / entry.name)
        if recheck is not None and version is not None:
            if clean_version(recheck()) != version:
                raise OwnRuntimeError("runtime.own.sourceChanged")
        if probe is not None:
            reported = clean_version(probe(staging / "ollama.exe"))
            if reported is None:
                raise OwnRuntimeError("runtime.own.probeFailed")
            if version is not None and reported != version:
                raise OwnRuntimeError("runtime.own.sourceChanged")
            version = reported
        assert version is not None
        marker = {"version": version, "source": str(source.exe.parent), "copiedAt": time.time()}
        (staging / COMPLETE_MARKER).write_text(json.dumps(marker), encoding="utf-8")
        target = root / version
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        os.replace(staging, target)
    except OwnRuntimeError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        log.exception("copying Ollama %s failed", version or "?")
        raise OwnRuntimeError("runtime.own.copyFailed") from exc
    log.info("Ollama %s copied to %s (%d entries in lib)", version, target, len(entries))
    return version


# --- processes --------------------------------------------------------------


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def pick_port(preferred: int = DEFAULT_PORT) -> int:
    return preferred if _port_free(preferred) else _free_port()


def daemon_env(exe: Path, port: int) -> dict[str, str]:
    from app.llm.blobs import models_dir
    from app.runtime.ollama_daemon import ollama_process_env

    env = ollama_process_env(exe)
    env["OLLAMA_HOST"] = f"127.0.0.1:{port}"
    # The same model folder as the installed Ollama (its GUI setting included),
    # so models pulled there or here are visible to both.
    env["OLLAMA_MODELS"] = str(models_dir())
    # Two servers share the folder. Pruning at start could delete a blob the
    # other one is still downloading; Agentus deletes models explicitly.
    env["OLLAMA_NOPRUNE"] = "1"
    return env


def _rotate_log(path: Path) -> None:
    try:
        if path.is_file() and path.stat().st_size > LOG_MAX_BYTES:
            os.replace(path, path.with_suffix(path.suffix + ".1"))
    except OSError:
        log.debug("could not rotate %s", path, exc_info=True)


def spawn_ollama(exe: Path, port: int, log_path: Path | None) -> tuple[subprocess.Popen, KillOnCloseJob]:
    env = daemon_env(exe, port)
    output: Any = subprocess.DEVNULL
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_log(log_path)
        output = open(log_path, "ab")  # noqa: SIM115 - the child keeps its own handle
    kwargs: dict[str, Any] = {
        "args": [str(exe), "serve"],
        "stdin": subprocess.DEVNULL,
        "stdout": output,
        "stderr": subprocess.STDOUT,
        "cwd": str(exe.parent),
        "env": env,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = _CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP
    try:
        proc = subprocess.Popen(**kwargs)
    finally:
        if output is not subprocess.DEVNULL:
            output.close()
    job = KillOnCloseJob()
    job.assign(getattr(proc, "_handle", None))
    return proc, job


def stop_process(proc: subprocess.Popen, job: KillOnCloseJob | None) -> None:
    try:
        if job is not None and job.active:
            job.terminate()
        elif proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    except Exception:
        log.debug("stopping Ollama failed", exc_info=True)


def fetch_version(port: int, *, timeout_sec: float = 1.5) -> str | None:
    try:
        with client(timeout_sec=timeout_sec) as http:
            response = http.get(f"http://127.0.0.1:{port}/api/version")
        if response.status_code != 200:
            return None
        body = response.json()
    except Exception:
        return None
    return clean_version(body.get("version")) if isinstance(body, dict) else None


def wait_until_ready(proc: subprocess.Popen, port: int, timeout_sec: float) -> str | None:
    """Version the new server reports, or None if it exits or stays silent."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return None
        version = fetch_version(port)
        if version is not None:
            return version
        time.sleep(0.3)
    return None


def probe_copy(exe: Path) -> str | None:
    """Start a staged copy once on a free port and read its version."""
    port = _free_port()
    proc, job = spawn_ollama(exe, port, None)
    try:
        return wait_until_ready(proc, port, PROBE_TIMEOUT_SEC)
    finally:
        stop_process(proc, job)


def _now() -> str:
    from app.db.engine import utc_now

    return utc_now()


# --- supervisor -------------------------------------------------------------


class _Daemon:
    def __init__(self, proc: subprocess.Popen, job: KillOnCloseJob) -> None:
        self.proc = proc
        self.job = job

    def alive(self) -> bool:
        return self.proc.poll() is None

    def stop(self) -> None:
        stop_process(self.proc, self.job)


class OwnOllama:
    """Start, watch and update the private copy. One instance per process."""

    def __init__(
        self,
        root: Path,
        *,
        log_path: Path | None = None,
        find: Callable[[], SourceInstall | None] | None = None,
        spawn: Callable[[Path, int, Path | None], tuple[Any, Any]] | None = None,
        ready: Callable[[Any, int, float], str | None] | None = None,
        probe: Callable[[Path], str | None] | None = None,
        kind: Callable[[Path], str | None] | None = None,
        fallback: Callable[[], None] | None = None,
        port: Callable[[], int] | None = None,
    ) -> None:
        self.root = root
        self.log_path = log_path
        self._find = find or (lambda: find_source(exclude=root))
        self._spawn = spawn or spawn_ollama
        self._ready = ready or wait_until_ready
        self._probe = probe or probe_copy
        self._kind = kind or backend_kind
        self._fallback = fallback or _start_external
        self._pick_port = port or pick_port
        self._lock = threading.RLock()
        self._op = threading.Lock()
        self._ready_event = threading.Event()
        self._threads = False
        self._stopping = False
        self._restarts: list[float] = []
        self.mode: Mode = "external"
        self.state: State = "disabled"
        self.port: int | None = None
        self.version: str | None = None
        self.folder: Path | None = None
        self.daemon: _Daemon | None = None
        self.source_version: str | None = None
        self.update_version: str | None = None
        self.staged_version: str | None = None
        self.checked_at: str | None = None
        self.message_key: str | None = None
        self.message_params: dict[str, str] = {}

    # read side, called on every Ollama request

    def active(self) -> bool:
        with self._lock:
            return self.mode == "own" and self.state in _ACTIVE and self.port is not None

    def root_url(self) -> str | None:
        with self._lock:
            if self.mode != "own" or self.state not in _ACTIVE or self.port is None:
                return None
            return f"http://127.0.0.1:{self.port}"

    def lib_dir(self) -> Path | None:
        with self._lock:
            if not self.active() or self.folder is None:
                return None
            return self.folder / "lib" / "ollama"

    def server_log(self) -> Path | None:
        return self.log_path if self.active() else None

    def wait_ready(self, timeout_sec: float) -> bool:
        with self._lock:
            waiting = self.mode == "own" and self.state in ("preparing", "starting")
        if not waiting:
            return True
        return self._ready_event.wait(timeout_sec)

    # boot

    def begin(self, mode: Mode) -> None:
        """Set mode and port before the slow part, so early requests go to the right place."""
        with self._lock:
            self.mode = mode
            self._stopping = False
            if mode != "own":
                self.state = "disabled"
                self._ready_event.set()
                return
            self.state = "preparing"
            self.port = self._pick_port()
            self._ready_event.clear()

    def boot(self) -> None:
        with self._op:
            self._boot_locked()

    def _boot_locked(self) -> None:
        state = read_state(self.root)
        if not is_complete(self.root / state.current if state.current else None):
            source = self._find()
            if source is None:
                self._give_up("unavailable", "runtime.own.noSource")
                return
            try:
                version = install_copy(
                    source,
                    self.root,
                    kind=self._kind(source.lib),
                    probe=None if clean_version(source.version) else self._probe,
                )
            except OwnRuntimeError as exc:
                self._give_up("failed", exc.key)
                return
            state = RuntimeState(current=version, failed=state.failed)
            write_state(self.root, state)
        assert state.current is not None
        started = self._start(state.current)
        if not started and is_complete(self.root / state.previous if state.previous else None):
            failed = state.current
            log.error("own Ollama %s did not start; going back to %s", failed, state.previous)
            state = RuntimeState(current=state.previous, previous=None, failed=failed)
            write_state(self.root, state)
            started = self._start(state.current or "")
            if started:
                self._message(
                    "runtime.own.rolledBack", {"failed": failed, "version": state.current or ""}
                )
        if not started:
            self._give_up("failed", "runtime.own.startFailed")
            return
        if state.pending:
            state.pending = False
            write_state(self.root, state)
            log.info("own Ollama %s confirmed after the update", state.current)
        prune_versions(self.root, {state.current, state.previous})
        try:
            # Reads the registry; the UI can show a waiting update right after the start.
            self.check_update()
        except Exception:
            log.debug("first Ollama update check failed", exc_info=True)
        self._start_threads()

    def _start(self, version: str) -> bool:
        folder = self.root / version
        with self._lock:
            self.state = "starting"
            self.folder = folder
            self.version = version
            port = self.port
        if port is None:
            return False
        try:
            proc, job = self._spawn(folder / "ollama.exe", port, self.log_path)
        except OSError:
            log.exception("could not start own Ollama %s", version)
            return False
        reported = self._ready(proc, port, START_TIMEOUT_SEC)
        if reported is None:
            log.error("own Ollama %s did not answer on port %s", version, port)
            stop_process(proc, job)
            return False
        if reported != version:
            log.warning("own Ollama in folder %s reports version %s", version, reported)
        with self._lock:
            self.daemon = _Daemon(proc, job)
            self.version = reported
            self.state = "running"
            self._ready_event.set()
        log.info("own Ollama %s listening on 127.0.0.1:%s", reported, port)
        return True

    def _give_up(self, state: State, key: str) -> None:
        with self._lock:
            self.state = state
            self.port = None
            self.folder = None
            self.daemon = None
            self.message_key = key
            self.message_params = {}
            self._ready_event.set()
        log.warning("own Ollama not available (%s); using the configured Ollama address", key)
        try:
            self._fallback()
        except Exception:
            log.debug("starting the external Ollama failed", exc_info=True)

    def _message(self, key: str, params: dict[str, str]) -> None:
        with self._lock:
            self.message_key = key
            self.message_params = dict(params)

    # background threads

    def _start_threads(self) -> None:
        with self._lock:
            if self._threads:
                return
            self._threads = True
        threading.Thread(target=self._supervise_loop, name="ollama-own", daemon=True).start()
        threading.Thread(target=self._check_loop, name="ollama-own-update", daemon=True).start()

    def _supervise_loop(self) -> None:
        while True:
            time.sleep(SUPERVISE_SEC)
            try:
                self.supervise_once()
            except Exception:
                log.exception("own Ollama supervisor failed")

    def supervise_once(self) -> None:
        """Restart a crashed daemon; give up after MAX_RESTARTS in RESTART_WINDOW_SEC."""
        with self._lock:
            daemon = self.daemon
            if self._stopping or self.state != "running" or daemon is None or daemon.alive():
                return
            code = daemon.proc.poll()
            now = time.monotonic()
            self._restarts = [stamp for stamp in self._restarts if now - stamp < RESTART_WINDOW_SEC]
            self._restarts.append(now)
            too_many = len(self._restarts) > MAX_RESTARTS
            self.daemon = None
            version = self.folder.name if self.folder is not None else self.version
        log.warning("own Ollama exited with code %s", code)
        if too_many or not version:
            self._give_up("failed", "runtime.own.crashed")
            return
        with self._op:
            if not self._start(version):
                self._give_up("failed", "runtime.own.crashed")

    def _check_loop(self) -> None:
        while True:
            time.sleep(CHECK_INTERVAL_SEC)
            try:
                self.check_update()
            except Exception:
                log.exception("Ollama update check failed")

    # updates

    def check_update(self) -> str | None:
        """Newer installed version than the copy, or None. Never offers a version that failed."""
        source = self._find()
        state = read_state(self.root)
        installed = clean_version(source.version) if source is not None else None
        offer = None
        if (
            installed is not None
            and state.current is not None
            and installed != state.failed
            and is_newer(installed, state.current)
        ):
            offer = installed
        with self._lock:
            before = self.update_version
            self.source_version = installed
            self.update_version = offer if self.staged_version != offer else None
            self.checked_at = _now()
        if offer is not None and before != offer:
            log.info("Ollama %s is installed; Agentus runs %s", offer, state.current)
        return offer

    def apply_update(self, *, run_busy: bool, download_running: bool) -> str:
        """Copy and test the installed version; it becomes current at the next start."""
        with self._lock:
            if self.mode != "own":
                raise OwnRuntimeError("runtime.own.notActive")
        if run_busy:
            raise OwnRuntimeError("runtime.own.busy")
        if download_running:
            raise OwnRuntimeError("runtime.own.downloadRunning")
        with self._op:
            source = self._find()
            state = read_state(self.root)
            if source is None or not is_newer(source.version, state.current):
                raise OwnRuntimeError("runtime.own.noUpdate")
            version = install_copy(
                source,
                self.root,
                kind=self._kind(source.lib),
                probe=self._probe,
                recheck=lambda: (self._find() or source).version,
            )
            old = self.root / state.current if state.current else None
            keep = state.current if is_complete(old) else None
            write_state(self.root, RuntimeState(current=version, previous=keep, pending=True))
            with self._lock:
                self.staged_version = version
                self.update_version = None
        log.info("Ollama %s is ready; Agentus switches at the next start", version)
        return version

    # shutdown

    def shutdown(self) -> None:
        with self._lock:
            self._stopping = True
            daemon = self.daemon
            self.daemon = None
            if self.mode == "own" and self.state in _ACTIVE:
                self.state = "stopped"
        if daemon is not None:
            daemon.stop()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self.mode,
                "state": self.state,
                "version": self.version if self.state in _ACTIVE else None,
                "port": self.port,
                "base_url": self.root_url(),
                "installed_version": self.source_version,
                "update_version": self.update_version,
                "staged_version": self.staged_version,
                "checked_at": self.checked_at,
                "message_key": self.message_key,
                "message_params": dict(self.message_params),
                "log_path": str(self.log_path) if self.log_path and self.state in _ACTIVE else None,
            }


# --- process-wide instance ------------------------------------------------------

_instance: OwnOllama | None = None
_instance_lock = threading.Lock()


def _start_external() -> None:
    from app.runtime.ollama_daemon import start_local_ollama_background

    start_local_ollama_background()


def get_own() -> OwnOllama:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = OwnOllama(runtime_root(), log_path=server_log_path())
        return _instance


def set_own_for_tests(instance: OwnOllama | None) -> None:
    global _instance
    with _instance_lock:
        _instance = instance


def own_root_url() -> str | None:
    instance = _instance
    return instance.root_url() if instance is not None else None


def own_server_log() -> Path | None:
    instance = _instance
    return instance.server_log() if instance is not None else None


def own_lib_dir() -> Path | None:
    instance = _instance
    return instance.lib_dir() if instance is not None else None


def wait_own_ollama(timeout_sec: float = 60.0) -> bool:
    """Run start: wait while the own copy is still being set up or started."""
    instance = _instance
    return instance.wait_ready(timeout_sec) if instance is not None else True


def configured_mode() -> Mode:
    try:
        from app.settings.service import load_settings

        mode = load_settings().ollama_runtime
    except Exception:
        return "external"
    return "own" if mode == "own" else "external"


def _disabled_by_env() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return os.environ.get("AGENTUS_NETWORK_NO_OLLAMA", "").strip().lower() in {"1", "true", "yes"}


def boot_ollama_runtime() -> None:
    """App start: own copy (default) or the external Ollama as before."""
    if _disabled_by_env():
        return
    mode = configured_mode()
    own = get_own()
    if mode != "own" or sys.platform != "win32":
        own.begin("external")
        _start_external()
        return
    own.begin("own")
    atexit.register(own.shutdown)

    def _run() -> None:
        try:
            own.boot()
        except Exception:
            log.exception("own Ollama boot failed")
            own._give_up("failed", "runtime.own.startFailed")

    threading.Thread(target=_run, name="ollama-own-boot", daemon=True).start()


def shutdown_ollama_runtime() -> None:
    instance = _instance
    if instance is not None:
        instance.shutdown()


def build_status() -> OwnOllamaStatus:
    from app.host.restart import can_restart
    from app.settings.service import is_run_busy

    own = get_own()
    snap = own.snapshot()
    configured = configured_mode()
    staged = snap.get("staged_version")
    return OwnOllamaStatus(
        **snap,
        configured_mode=configured,
        restart_required=configured != snap["mode"] or bool(staged),
        can_restart=can_restart(),
        run_busy=is_run_busy(),
        download_running=download_running(),
    )


def download_running() -> bool:
    try:
        from app.llm.downloads import list_downloads

        return any(item.status == "running" for item in list_downloads().items)
    except Exception:
        return False
