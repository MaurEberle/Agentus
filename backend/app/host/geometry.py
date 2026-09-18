from __future__ import annotations

from dataclasses import dataclass

MIN_W, MIN_H = 800, 560
MARGIN = 24


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


def work_area() -> Rect:
    try:
        import ctypes
        from ctypes import wintypes

        SPI_GETWORKAREA = 16
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        return Rect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        return Rect(0, 0, 1280, 720)


def default_rect() -> Rect:
    area = work_area()
    w = max(MIN_W, area.w - 2 * MARGIN)
    h = max(MIN_H, area.h - 2 * MARGIN)
    x = area.x + MARGIN
    y = area.y + MARGIN
    return clamp_to_visible(Rect(x, y, w, h))


def clamp_to_visible(r: Rect) -> Rect:
    area = work_area()
    w = max(MIN_W, r.w)
    h = max(MIN_H, r.h)
    intersects = not (
        r.x + r.w <= area.x
        or r.x >= area.x + area.w
        or r.y + r.h <= area.y
        or r.y >= area.y + area.h
    )
    if not intersects:
        return default_rect()
    x = min(max(r.x, area.x), area.x + max(0, area.w - MIN_W))
    y = min(max(r.y, area.y), area.y + max(0, area.h - MIN_H))
    if x + w > area.x + area.w:
        x = area.x + area.w - w
    if y + h > area.y + area.h:
        y = area.y + area.h - h
    x = max(area.x, x)
    y = max(area.y, y)
    return Rect(x, y, w, h)


def from_bootstrap(window) -> Rect:
    w = int(getattr(window, "w", 0) or 0)
    h = int(getattr(window, "h", 0) or 0)
    if w == 0 or h == 0:
        return default_rect()
    return clamp_to_visible(
        Rect(
            int(getattr(window, "x", 0) or 0),
            int(getattr(window, "y", 0) or 0),
            w,
            h,
        )
    )
