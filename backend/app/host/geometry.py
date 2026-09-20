from __future__ import annotations

from dataclasses import dataclass

MIN_W, MIN_H = 1280, 720
MARGIN = 24
_FALLBACK_W, _FALLBACK_H = 1440, 900
_WIDTH_RATIO = 0.86
_HEIGHT_RATIO = 0.92


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


def work_area() -> Rect:
    fallback = Rect(0, 0, _FALLBACK_W, _FALLBACK_H)
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        ok = ctypes.windll.user32.SystemParametersInfoW(16, 0, ctypes.byref(rect), 0)
        if not ok:
            return fallback
        w = int(rect.right) - int(rect.left)
        h = int(rect.bottom) - int(rect.top)
        if w <= 0 or h <= 0:
            return fallback
        return Rect(int(rect.left), int(rect.top), w, h)
    except Exception:
        return fallback


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


def default_rect() -> Rect:
    area = work_area()
    max_w = max(MIN_W, area.w - 2 * MARGIN)
    max_h = max(MIN_H, area.h - 2 * MARGIN)
    w = min(max_w, max(MIN_W, int(area.w * _WIDTH_RATIO)))
    h = min(max_h, max(MIN_H, int(area.h * _HEIGHT_RATIO)))
    x = area.x + max(0, (area.w - w) // 2)
    y = area.y + max(0, (area.h - h) // 2)
    return _fit(area, Rect(x, y, w, h))


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
