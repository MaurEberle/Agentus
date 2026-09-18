from __future__ import annotations

import threading
import time

from app.db.engine import utc_now
from app.run.limits import RESOURCES_INTERVAL_SEC
from app.run.models import ResourceSnapshot
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
    gpus = None
    try:
        import pynvml

        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        gpus = []
        for index in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            name = None
            try:
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode()
            except Exception:
                pass
            from app.run.models import ResourceGpu

            gpus.append(
                ResourceGpu(
                    index=index,
                    name=name,
                    util_percent=float(util.gpu),
                    vram_used_bytes=int(mem.used),
                    vram_total_bytes=int(mem.total),
                )
            )
    except Exception:
        gpus = None
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


def start_resources() -> None:
    global _thread
    _stop.clear()
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, name="run-resources", daemon=True)
    _thread.start()


def stop_resources() -> None:
    _stop.set()
