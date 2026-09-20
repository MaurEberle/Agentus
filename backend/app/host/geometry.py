from __future__ import annotations

from dataclasses import dataclass

MIN_W, MIN_H = 1280, 720
MARGIN = 24
_FALLBACK_W, _FALLBACK_H = 1440, 900
RATIO_LARGE = 0.65
RATIO_MEDIUM = 0.75
RATIO_FULL = 1.0
_MONITOR_DEFAULTTOPRIMARY = 1


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


def _from_win_rect(rect: object) -> Rect | None:
    left = int(getattr(rect, "left", 0))
    top = int(getattr(rect, "top", 0))
    right = int(getattr(rect, "right", 0))
    bottom = int(getattr(rect, "bottom", 0))
    w = right - left
    h = bottom - top
    if w <= 0 or h <= 0:
        return None
    return Rect(left, top, w, h)


def display() -> tuple[Rect, Rect]:
    """Pixel size and work area of the monitor under the cursor (else primary)."""
    fallback = Rect(0, 0, _FALLBACK_W, _FALLBACK_H)
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        pt = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(pt)):
            pt.x, pt.y = 0, 0
        handle = user32.MonitorFromPoint(pt, _MONITOR_DEFAULTTOPRIMARY)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if handle and user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            monitor = _from_win_rect(info.rcMonitor)
            work = _from_win_rect(info.rcWork)
            if monitor is not None:
                return monitor, work or monitor

        spi = wintypes.RECT()
        if user32.SystemParametersInfoW(16, 0, ctypes.byref(spi), 0):
            work = _from_win_rect(spi)
            if work is not None:
                return work, work

        w = int(user32.GetSystemMetrics(0))
        h = int(user32.GetSystemMetrics(1))
        if w > 0 and h > 0:
            screen = Rect(0, 0, w, h)
            return screen, screen
    except Exception:
        pass
    return fallback, fallback


def work_area() -> Rect:
    return display()[1]


def _fit(area: Rect, r: Rect) -> Rect:
    """Pin r onto area. Never calls default_rect (avoids recursion)."""
    w = max(MIN_W, r.w)
    h = max(MIN_H, r.h)
    x = min(max(r.x, area.x), area.x + max(0, area.w - MIN_W))
    y = min(max(r.y, area.y), area.y + max(0, area.h - MIN_H))
    if x + w > area.x + area.w:
        x = area.x + area.w - w
    if y + h > area.y + area.h:
        y = area.y + area.h - h
    x = max(area.x, x)
    y = max(area.y, y)
    return Rect(x, y, w, h)


def size_ratio(monitor: Rect) -> float:
    """Desktop start scale vs monitor pixels. Large 65%, medium 75%, else fullscreen."""
    if int(monitor.w * RATIO_LARGE) >= MIN_W and int(monitor.h * RATIO_LARGE) >= MIN_H:
        return RATIO_LARGE
    if int(monitor.w * RATIO_MEDIUM) >= MIN_W and int(monitor.h * RATIO_MEDIUM) >= MIN_H:
        return RATIO_MEDIUM
    return RATIO_FULL


def start_placement() -> tuple[Rect, bool]:
    """Centered start rect and whether the desktop window should maximize."""
    monitor, work = display()
    ratio = size_ratio(monitor)
    if ratio >= RATIO_FULL:
        return _fit(work, Rect(work.x, work.y, work.w, work.h)), True
    w = max(MIN_W, int(monitor.w * ratio))
    h = max(MIN_H, int(monitor.h * ratio))
    max_w = max(MIN_W, work.w - 2 * MARGIN)
    max_h = max(MIN_H, work.h - 2 * MARGIN)
    w = min(w, max_w)
    h = min(h, max_h)
    x = work.x + max(0, (work.w - w) // 2)
    y = work.y + max(0, (work.h - h) // 2)
    return _fit(work, Rect(x, y, w, h)), False


def default_rect() -> Rect:
    return start_placement()[0]


def clamp_to_visible(r: Rect) -> Rect:
    area = work_area()
    intersects = not (
        r.x + r.w <= area.x
        or r.x >= area.x + area.w
        or r.y + r.h <= area.y
        or r.y >= area.y + area.h
    )
    if not intersects:
        return default_rect()
    return _fit(area, r)


def from_bootstrap(window) -> Rect:
    return default_rect()
