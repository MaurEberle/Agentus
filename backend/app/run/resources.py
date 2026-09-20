from __future__ import annotations

import sys
import threading
import time

from app.db.engine import utc_now
from app.run.limits import RESOURCES_INTERVAL_SEC
from app.run.models import ResourceGpu, ResourceSnapshot
from app.run.sse import publish

_stop = threading.Event()
_thread: threading.Thread | None = None


def _sample() -> ResourceSnapshot:
    cpu = 0.0
    ram_used = 0
    ram_total = 0
    try:
        import psutil

        cpu = float(psutil.cpu_percent(interval=None))
        mem = psutil.virtual_memory()
        ram_used = int(mem.used)
        ram_total = int(mem.total)
    except Exception:
        pass
    gpus: list[ResourceGpu] | None
    sampled = _sample_gpus()
    gpus = sampled if sampled else None
    return ResourceSnapshot(
        ts=utc_now(),
        cpu_percent=cpu,
        ram_used_bytes=ram_used,
        ram_total_bytes=ram_total,
        gpus=gpus,
        scope="host",
    )


def _loop() -> None:
    try:
        import psutil

        psutil.cpu_percent(interval=None)
    except Exception:
        pass
    while not _stop.wait(RESOURCES_INTERVAL_SEC):
        snap = _sample()
        publish("resources", snap.model_dump(by_alias=True))
        try:
            from app.db.runs import touch_run
            from app.run.controller import get_controller

            run_id = get_controller().run_id
            if run_id:
                touch_run(run_id, at=snap.ts)
        except Exception:
            pass


def _sample_gpus() -> list[ResourceGpu]:
    rows: list[dict[str, object]] = []
    if sys.platform == "win32":
        try:
            from app.run.gpu_win import sample_gpus

            rows = sample_gpus()
        except Exception:
            rows = []
    if not rows:
        rows = _sample_nvml()
    out: list[ResourceGpu] = []
    for row in rows:
        try:
            out.append(
                ResourceGpu(
                    index=int(row["index"]),
                    name=str(row["name"]) if row.get("name") else None,
                    util_percent=float(row["util_percent"]),
                    vram_used_bytes=int(row["vram_used_bytes"]),
                    vram_total_bytes=int(row["vram_total_bytes"]),
                )
            )
        except Exception:
            continue
    return out


def _sample_nvml() -> list[dict[str, object]]:
    try:
        import pynvml
    except Exception:
        return []
    try:
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        gpus: list[dict[str, object]] = []
        for index in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            name: str | None = None
            try:
                raw = pynvml.nvmlDeviceGetName(handle)
                name = raw.decode() if isinstance(raw, bytes) else str(raw)
            except Exception:
                name = None
            gpus.append(
                {
                    "index": index,
                    "name": name,
                    "util_percent": float(util.gpu),
                    "vram_used_bytes": int(mem.used),
                    "vram_total_bytes": int(mem.total),
                }
            )
        return gpus
    except Exception:
        return []


def start_resources() -> None:
    global _thread
    _stop.clear()
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, name="run-resources", daemon=True)
    _thread.start()


def stop_resources() -> None:
    _stop.set()
    if sys.platform == "win32":
        try:
            from app.run.gpu_win import close_sampler

            close_sampler()
        except Exception:
            pass
