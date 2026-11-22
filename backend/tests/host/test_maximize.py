from __future__ import annotations

from app.host.geometry import Rect
from app.host.maximize import max_bounds, maximized_rect

FRAME = (7, 7, 7, 7)
PRIMARY = Rect(0, 0, 2560, 1440)


def _windows_applies(bounds: Rect, monitor: Rect, primary: Rect) -> Rect:
    """What WM_GETMINMAXINFO makes of the bounds on `monitor` (Raymond Chen, 2015-05-01)."""
    w, h = bounds.w, bounds.h
    if w >= primary.w and h >= primary.h:
        w += monitor.w - primary.w
        h += monitor.h - primary.h
    return Rect(monitor.x + bounds.x, monitor.y + bounds.y, w, h)


def test_maximized_rect_puts_the_frame_outside_the_work_area() -> None:
    work = Rect(0, 0, 2560, 1400)
    assert maximized_rect(work, FRAME) == Rect(-7, -7, 2574, 1414)


def test_single_monitor_leaves_the_taskbar_free() -> None:
    work = Rect(0, 0, 2560, 1400)
    bounds = max_bounds(PRIMARY, work, PRIMARY, FRAME)
    assert bounds == Rect(-7, -7, 2574, 1414)
    assert _windows_applies(bounds, PRIMARY, PRIMARY) == maximized_rect(work, FRAME)


def test_taskbar_on_top_shifts_the_window_down() -> None:
    work = Rect(0, 40, 2560, 1400)
    bounds = max_bounds(PRIMARY, work, PRIMARY, FRAME)
    assert bounds == Rect(-7, 33, 2574, 1414)


def test_bigger_second_monitor_without_taskbar_is_sized_for_windows_to_grow() -> None:
    monitor = Rect(2560, 0, 3840, 2160)
    bounds = max_bounds(monitor, monitor, PRIMARY, FRAME)
    assert bounds == Rect(-7, -7, 2574, 1454)
    assert _windows_applies(bounds, monitor, PRIMARY) == maximized_rect(monitor, FRAME)


def test_smaller_second_monitor_with_taskbar_is_used_as_is() -> None:
    monitor = Rect(-1920, 0, 1920, 1080)
    work = Rect(-1920, 0, 1920, 1040)
    bounds = max_bounds(monitor, work, PRIMARY, FRAME)
    assert bounds == Rect(-7, -7, 1934, 1054)
    assert _windows_applies(bounds, monitor, PRIMARY) == maximized_rect(work, FRAME)


def test_bigger_second_monitor_with_taskbar_is_left_for_the_correction() -> None:
    # No size survives Windows' adjustment here; keep_off_taskbar moves the window afterwards.
    monitor = Rect(2560, 0, 3840, 2160)
    work = Rect(2560, 0, 3840, 2120)
    bounds = max_bounds(monitor, work, PRIMARY, FRAME)
    assert bounds == Rect(-7, -7, 3854, 2134)
