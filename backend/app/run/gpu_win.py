"""Host GPU stats on Windows via DXGI (adapters) and PDH (util + VRAM).

Covers NVIDIA, AMD, and Intel WDDM adapters. No extra pip packages.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Any

_LUID_RE = re.compile(r"luid_0x([0-9a-fA-F]+)_0x([0-9a-fA-F]+)", re.I)
_ENGTYPE_RE = re.compile(r"engtype_(.+)$", re.I)

MICROSOFT_VENDOR = 0x1414
KNOWN_VENDORS = {0x10DE, 0x1002, 0x8086}  # NVIDIA, AMD, Intel
MIN_DEDICATED = 128 * 1024 * 1024
BUSY_ENGINES = ("3D", "Compute")

_lock = threading.Lock()
_session: _PdhSession | None = None


@dataclass(frozen=True)
class GpuAdapter:
    luid: str
    name: str
    vendor_id: int
    dedicated_bytes: int
    shared_bytes: int


def luid_key(high: int, low: int) -> str:
    return f"{high & 0xFFFFFFFF:08x}_{low & 0xFFFFFFFF:08x}"


def parse_luid(instance: str) -> str | None:
    match = _LUID_RE.search(instance or "")
    if not match:
        return None
    return luid_key(int(match.group(1), 16), int(match.group(2), 16))


def parse_engtype(instance: str) -> str:
    match = _ENGTYPE_RE.search(instance or "")
    return match.group(1).strip() if match else ""


def is_busy_engine(engtype: str) -> bool:
    text = engtype.lower()
    return "3d" in text or "compute" in text


def include_adapter(vendor_id: int, name: str, dedicated: int) -> bool:
    if vendor_id == MICROSOFT_VENDOR:
        return False
    lowered = name.lower()
    if "basic render" in lowered or "microsoft basic" in lowered:
        return False
    if vendor_id in KNOWN_VENDORS:
        return True
    return dedicated >= MIN_DEDICATED


def merge_util(engine_rows: list[tuple[str, str, float]]) -> dict[str, float]:
    """Sum per-process util per (luid, engine type), then take the busiest engine."""
    by_type: dict[tuple[str, str], float] = {}
    for luid, engtype, value in engine_rows:
        if not luid or not is_busy_engine(engtype):
            continue
        key = (luid, engtype.lower())
        by_type[key] = by_type.get(key, 0.0) + max(0.0, value)
    best: dict[str, float] = {}
    for (luid, _kind), total in by_type.items():
        best[luid] = max(best.get(luid, 0.0), min(100.0, total))
    return best


def merge_vram(rows: list[tuple[str, float]]) -> dict[str, int]:
    used: dict[str, int] = {}
    for luid, value in rows:
        if not luid:
            continue
        used[luid] = max(used.get(luid, 0), int(max(0.0, value)))
    return used


def _invoke(this: Any, index: int, restype: Any, argtypes: list[Any], *args: Any) -> Any:
    import ctypes
    from ctypes import POINTER, c_void_p

    lp_vtbl = ctypes.cast(this, POINTER(c_void_p))[0]
    fnptr = ctypes.cast(lp_vtbl, POINTER(c_void_p))[index]
    fn = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(fnptr)
    return fn(this, *args)


def list_adapters() -> list[GpuAdapter]:
    import ctypes
    import uuid
    from ctypes import POINTER, c_long, c_uint, c_void_p, c_wchar, wintypes

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

    class DXGI_ADAPTER_DESC(ctypes.Structure):
        _fields_ = [
            ("Description", c_wchar * 128),
            ("VendorId", wintypes.UINT),
            ("DeviceId", wintypes.UINT),
            ("SubSysId", wintypes.UINT),
            ("Revision", wintypes.UINT),
            ("DedicatedVideoMemory", ctypes.c_size_t),
            ("DedicatedSystemMemory", ctypes.c_size_t),
            ("SharedSystemMemory", ctypes.c_size_t),
            ("AdapterLuid", LUID),
        ]

    dxgi = ctypes.WinDLL("dxgi")
    create = dxgi.CreateDXGIFactory1
    create.argtypes = [ctypes.c_void_p, POINTER(c_void_p)]
    create.restype = c_long
    iid = uuid.UUID("{770aae78-f26f-4dba-a829-253c83d1b387}")
    iid_buf = (ctypes.c_ubyte * 16).from_buffer_copy(iid.bytes_le)
    factory = c_void_p()
    if create(ctypes.byref(iid_buf), ctypes.byref(factory)) != 0 or not factory.value:
        return []
    out: list[GpuAdapter] = []
    try:
        for index in range(16):
            adapter = c_void_p()
            hr = _invoke(factory, 7, c_long, [c_uint, POINTER(c_void_p)], index, ctypes.byref(adapter))
            if hr != 0 or not adapter.value:
                break
            try:
                desc = DXGI_ADAPTER_DESC()
                if _invoke(adapter, 8, c_long, [POINTER(DXGI_ADAPTER_DESC)], ctypes.byref(desc)) != 0:
                    continue
                name = str(desc.Description).strip()
                dedicated = int(desc.DedicatedVideoMemory)
                if not include_adapter(int(desc.VendorId), name, dedicated):
                    continue
                out.append(
                    GpuAdapter(
                        luid=luid_key(int(desc.AdapterLuid.HighPart), int(desc.AdapterLuid.LowPart)),
                        name=name,
                        vendor_id=int(desc.VendorId),
                        dedicated_bytes=dedicated,
                        shared_bytes=int(desc.SharedSystemMemory),
                    )
                )
            finally:
                _invoke(adapter, 2, c_uint, [])
    finally:
        _invoke(factory, 2, c_uint, [])
    return out


class _PdhSession:
    def __init__(self) -> None:
        import ctypes
        from ctypes import POINTER, c_long, c_void_p, wintypes

        self._ctypes = ctypes
        self._pdh = ctypes.WinDLL("pdh")
        self._query = c_void_p()
        self._util = c_void_p()
        self._vram = c_void_p()
        self._ready = False
        open_q = self._pdh.PdhOpenQueryW
        open_q.argtypes = [wintypes.LPCWSTR, c_void_p, POINTER(c_void_p)]
        open_q.restype = c_long
        add = self._pdh.PdhAddEnglishCounterW
        add.argtypes = [c_void_p, wintypes.LPCWSTR, c_void_p, POINTER(c_void_p)]
        add.restype = c_long
        collect = self._pdh.PdhCollectQueryData
        collect.argtypes = [c_void_p]
        collect.restype = c_long
        if open_q(None, None, ctypes.byref(self._query)) != 0:
            return
        if add(self._query, r"\GPU Engine(*)\Utilization Percentage", None, ctypes.byref(self._util)) != 0:
            self.close()
            return
        add(self._query, r"\GPU Adapter Memory(*)\Dedicated Usage", None, ctypes.byref(self._vram))
        collect(self._query)
        self._ready = True

    def close(self) -> None:
        if getattr(self, "_query", None) and self._query.value:
            close = self._pdh.PdhCloseQuery
            close.argtypes = [self._ctypes.c_void_p]
            close.restype = self._ctypes.c_long
            close(self._query)
        self._query = None
        self._ready = False

    def collect(self) -> tuple[list[tuple[str, str, float]], list[tuple[str, float]]]:
        if not self._ready:
            return [], []
        import ctypes
        from ctypes import POINTER, c_double, c_long, c_void_p, wintypes

        class PDH_FMT_COUNTERVALUE(ctypes.Structure):
            _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", c_double)]

        class PDH_FMT_COUNTERVALUE_ITEM_W(ctypes.Structure):
            _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", PDH_FMT_COUNTERVALUE)]

        collect = self._pdh.PdhCollectQueryData
        collect.argtypes = [c_void_p]
        collect.restype = c_long
        collect(self._query)
        fmt = 0x00000200 | 0x00008000  # DOUBLE | NOCAP100
        get_arr = self._pdh.PdhGetFormattedCounterArrayW
        get_arr.argtypes = [c_void_p, wintypes.DWORD, POINTER(wintypes.DWORD), POINTER(wintypes.DWORD), c_void_p]
        get_arr.restype = c_long

        def read(counter: Any) -> list[tuple[str, float]]:
            if not counter or not counter.value:
                return []
            bufsize = wintypes.DWORD(0)
            count = wintypes.DWORD(0)
            get_arr(counter, fmt, ctypes.byref(bufsize), ctypes.byref(count), None)
            if bufsize.value == 0:
                return []
            buf = (ctypes.c_byte * bufsize.value)()
            status = get_arr(counter, fmt, ctypes.byref(bufsize), ctypes.byref(count), buf)
            if status != 0:
                return []
            items = ctypes.cast(buf, POINTER(PDH_FMT_COUNTERVALUE_ITEM_W))
            rows: list[tuple[str, float]] = []
            for i in range(count.value):
                item = items[i]
                name = item.szName or ""
                if item.FmtValue.CStatus != 0:
                    continue
                rows.append((name, float(item.FmtValue.doubleValue)))
            return rows

        util_raw = read(self._util)
        engines = [(parse_luid(name) or "", parse_engtype(name), value) for name, value in util_raw]
        vram_raw = read(self._vram)
        vram = [(parse_luid(name) or "", value) for name, value in vram_raw]
        return engines, vram


def _session_locked() -> _PdhSession | None:
    global _session
    if _session is None:
        try:
            _session = _PdhSession()
        except Exception:
            _session = None
    if _session is not None and not _session._ready:
        _session = None
    return _session


def close_sampler() -> None:
    global _session
    with _lock:
        if _session is not None:
            try:
                _session.close()
            except Exception:
                pass
            _session = None


def sample_gpus() -> list[dict[str, Any]]:
    """Return ResourceGpu-shaped dicts (snake_case) for the host adapters."""
    try:
        adapters = list_adapters()
    except Exception:
        adapters = []
    if not adapters:
        return []
    engines: list[tuple[str, str, float]] = []
    vram_rows: list[tuple[str, float]] = []
    with _lock:
        session = _session_locked()
        if session is not None:
            try:
                engines, vram_rows = session.collect()
            except Exception:
                engines, vram_rows = [], []
    util = merge_util(engines)
    vram = merge_vram(vram_rows)
    gpus: list[dict[str, Any]] = []
    for index, adapter in enumerate(adapters):
        total = adapter.dedicated_bytes or adapter.shared_bytes
        used = min(vram.get(adapter.luid, 0), total) if total else vram.get(adapter.luid, 0)
        gpus.append(
            {
                "index": index,
                "name": adapter.name,
                "util_percent": util.get(adapter.luid, 0.0),
                "vram_used_bytes": used,
                "vram_total_bytes": total,
            }
        )
    return gpus
