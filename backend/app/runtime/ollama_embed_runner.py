"""Start llama-server with --embedding when Ollama will not.

Ollama 0.34 enables that flag only if the GGUF contains pooling_type.
Qwen3-VL-Embedding ships without it, so /v1/embeddings returns 501 even
though the weights are an embedding model. This module loads the same
blobs with --pooling last, serves one local runner, and stops it when idle.
"""

from __future__ import annotations

import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from app.common.http import client
from app.runtime.errors import RuntimeApiError
from app.runtime.models import EmbedRequest, EmbedResult

log = logging.getLogger("agentus.runtime.embed")

_CREATE_NO_WINDOW = 0x08000000
_IDLE_SEC = 45.0
_BATCH = 16
_CTX = "4096"

_lock = threading.Lock()
_runner: "_Runner | None" = None
_idle_started = False


class _Runner:
    def __init__(self, proc: subprocess.Popen[bytes], port: int, signature: tuple[str, ...]) -> None:
        self.proc = proc
        self.port = port
        self.signature = signature
        self.refs = 0
        self.last_used = time.monotonic()

    def alive(self) -> bool:
        return self.proc.poll() is None


def reset_for_tests() -> None:
    global _runner, _idle_started
    with _lock:
        _stop_locked()
        _idle_started = False


def gguf_paths_from_modelfile(text: str) -> list[Path]:
    paths: list[Path] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("FROM "):
            continue
        raw = stripped[5:].strip().strip('"').strip("'")
        if not raw or raw.startswith("#"):
            continue
        path = Path(raw)
        if path.is_file():
            paths.append(path)
    return paths


def llama_server_exe() -> Path | None:
    candidates: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "Ollama" / "lib" / "ollama" / "llama-server.exe")
    which = shutil.which("ollama")
    if which:
        candidates.append(Path(which).resolve().parent / "lib" / "ollama" / "llama-server.exe")
    for path in candidates:
        if path.is_file():
            return path
    return None


def embed_with_forced_runner(req: EmbedRequest) -> EmbedResult:
    from app.runtime.embeddings import _embed_batched

    root = _ollama_root()
    files = _model_files(root, req.model)
    exe = llama_server_exe()
    if not files or exe is None:
        raise RuntimeApiError("runtime.embedUnsupported")
    _unload(root, req.model)
    signature = tuple(str(path) for path in files)
    port = _acquire(exe, files, signature)
    try:
        local = req.model_copy(
            update={
                "base_url": f"http://127.0.0.1:{port}",
                "provider": "ollama",
                "credential_id": None,
                "secret": None,
            }
        )
        return _embed_batched(local, batch_size=_BATCH)
    finally:
        _release()


def _ollama_root() -> str:
    try:
        from app.runtime.urls import settings_roots

        root, _openai = settings_roots()
        return root.rstrip("/")
    except Exception:
        return "http://127.0.0.1:11434"


def _model_files(root: str, model: str) -> list[Path]:
    try:
        with client(timeout_sec=15) as http:
            response = http.post(f"{root}/api/show", json={"model": model})
        if response.status_code != 200:
            return []
        body = response.json()
    except Exception:
        return []
    modelfile = body.get("modelfile") if isinstance(body, dict) else None
    if not isinstance(modelfile, str):
        return []
    return gguf_paths_from_modelfile(modelfile)


def _unload(root: str, model: str) -> None:
    try:
        with client(timeout_sec=20) as http:
            http.post(
                f"{root}/api/generate",
                json={"model": model, "keep_alive": 0, "stream": False},
            )
    except Exception:
        log.info("could not unload ollama model before embedding runner")
        return
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if not _model_loaded(root, model):
            return
        time.sleep(0.4)


def _model_loaded(root: str, model: str) -> bool:
    try:
        with client(timeout_sec=5) as http:
            response = http.get(f"{root}/api/ps")
        if response.status_code != 200:
            return False
        body = response.json()
    except Exception:
        return False
    rows = body.get("models") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        return False
    wanted = model.lower()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("model") or "").lower()
        if name == wanted:
            return True
    return False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _acquire(exe: Path, files: list[Path], signature: tuple[str, ...]) -> int:
    global _runner
    with _lock:
        _ensure_idle_thread()
        current = _runner
        if current is not None and current.signature == signature and current.alive():
            current.refs += 1
            current.last_used = time.monotonic()
            return current.port
        _stop_locked()
        port = _free_port()
        proc = _spawn(exe, files, port)
        runner = _Runner(proc, port, signature)
        if not _wait_ready(runner, timeout_sec=120):
            _stop_process(proc)
            raise RuntimeApiError("runtime.embedUnsupported")
        runner.refs = 1
        runner.last_used = time.monotonic()
        _runner = runner
        log.info("started embedding llama-server on port %s", port)
        return port


def _release() -> None:
    with _lock:
        if _runner is not None and _runner.refs > 0:
            _runner.refs -= 1
            _runner.last_used = time.monotonic()


def _spawn(exe: Path, files: list[Path], port: int) -> subprocess.Popen[bytes]:
    args = [
        str(exe),
        "--model",
        str(files[0]),
        "--port",
        str(port),
        "--host",
        "127.0.0.1",
        "--no-webui",
        "--offline",
        "-c",
        _CTX,
        "-np",
        "1",
        "--embedding",
        "--pooling",
        "last",
        "--flash-attn",
        "auto",
        "-b",
        "512",
        "-ub",
        "512",
        "--log-verbosity",
        "1",
    ]
    if len(files) > 1:
        args.extend(["--mmproj", str(files[1]), "--image-min-tokens", "1024"])
    kwargs: dict[str, object] = {
        "args": args,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": str(exe.parent),
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = _CREATE_NO_WINDOW
    return subprocess.Popen(**kwargs)  # type: ignore[arg-type]


def _wait_ready(runner: _Runner, *, timeout_sec: float) -> bool:
    deadline = time.monotonic() + timeout_sec
    url = f"http://127.0.0.1:{runner.port}/health"
    while time.monotonic() < deadline:
        if not runner.alive():
            return False
        try:
            with client(timeout_sec=2) as http:
                response = http.get(url)
            if response.status_code == 200 and "ok" in response.text.lower():
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def _ensure_idle_thread() -> None:
    global _idle_started
    if _idle_started:
        return
    _idle_started = True
    threading.Thread(target=_idle_loop, name="embed-runner", daemon=True).start()


def _idle_loop() -> None:
    while True:
        time.sleep(5)
        with _lock:
            current = _runner
            if current is None or current.refs > 0:
                continue
            if time.monotonic() - current.last_used < _IDLE_SEC:
                continue
            _stop_locked()


def _stop_locked() -> None:
    global _runner
    current = _runner
    _runner = None
    if current is not None:
        _stop_process(current.proc)


def _stop_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
    else:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
