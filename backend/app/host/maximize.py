"""Keep the maximized frameless window off the taskbar.

Windows maximizes a window without a caption over the whole monitor, taskbar included.
WinForms' ``MaximizedBounds`` feeds WM_GETMINMAXINFO, so we set it to the work area of the
window's monitor, grown by the resize frame (``enable_frameless_resize`` adds WS_THICKFRAME,
about 7 px a side) so that the client area, not the frame, fills the work area.

WM_GETMINMAXINFO speaks in terms of the primary monitor: the position is moved to the
target monitor, and a size at least as big as the primary monitor grows by how much bigger
the target is. Where that rule cannot express the size we want (a bigger second monitor
with its own taskbar), ``keep_off_taskbar`` moves the maximized window into place afterwards.
"""

from __future__ import annotations

import logging
from typing import Any

from app.host.geometry import Rect
from app.host.native_frame import _hwnd

log = logging.getLogger("agentus.host")

Insets = tuple[int, int, int, int]  # left, top, right, bottom

_MONITOR_DEFAULTTONEAREST = 2
_MONITOR_DEFAULTTOPRIMARY = 1
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_SW_SHOWNORMAL = 1


def maximized_rect(work: Rect, insets: Insets) -> Rect:
    """Screen rect of the maximized window: the work area plus the frame around the client."""
    left, top, right, bottom = insets
    return Rect(work.x - left, work.y - top, work.w + left + right, work.h + top + bottom)


def max_bounds(monitor: Rect, work: Rect, primary: Rect, insets: Insets) -> Rect:
    """``MaximizedBounds`` for a window on ``monitor``, as WM_GETMINMAXINFO reads it."""
    target = maximized_rect(work, insets)
    x, y, w, h = target.x - monitor.x, target.y - monitor.y, target.w, target.h
    if w >= primary.w and h >= primary.h:
        # Windows grows a size that covers the primary monitor by the difference to this one;
        # hand it the smaller size when that still covers the primary monitor.
        w2 = w - (monitor.w - primary.w)
        h2 = h - (monitor.h - primary.h)
        if w2 >= primary.w and h2 >= primary.h:
            w, h = w2, h2
    return Rect(x, y, w, h)


def _user32() -> Any:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user32.MonitorFromPoint.restype = wintypes.HMONITOR
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.IsZoomed.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.GetWindowPlacement.restype = wintypes.BOOL
    user32.SetWindowPlacement.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.SetWindowPlacement.restype = wintypes.BOOL
    return user32


def _rect(raw: Any) -> Rect:
    return Rect(int(raw.left), int(raw.top), int(raw.right - raw.left), int(raw.bottom - raw.top))


def _monitor_info(user32: Any, handle: Any) -> tuple[Rect, Rect] | None:
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    if not handle:
        return None
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
        return None
    return _rect(info.rcMonitor), _rect(info.rcWork)


def _window_rect(user32: Any, hwnd: int) -> Rect:
    import ctypes
    from ctypes import wintypes

    raw = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(raw))
    return _rect(raw)


def _insets(user32: Any, hwnd: int) -> Insets | None:
    """Frame between window rect and client area; None while minimized."""
    import ctypes
    from ctypes import wintypes

    if user32.IsIconic(hwnd):
        return None
    outer = _window_rect(user32, hwnd)
    client = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(client))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    left = origin.x - outer.x
    top = origin.y - outer.y
    right = outer.x + outer.w - (origin.x + client.right)
    bottom = outer.y + outer.h - (origin.y + client.bottom)
    if min(left, top, right, bottom) < 0:
        return None
    return left, top, right, bottom


def _placement(window: Any) -> tuple[Any, int, Rect, Rect, Rect, Insets] | None:
    """user32, hwnd, monitor, work area, primary monitor and frame of the window."""
    from ctypes import wintypes

    hwnd = _hwnd(window)
    if not hwnd:
        return None
    user32 = _user32()
    current = _monitor_info(user32, user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONEAREST))
    primary = _monitor_info(user32, user32.MonitorFromPoint(wintypes.POINT(0, 0), _MONITOR_DEFAULTTOPRIMARY))
    insets = _insets(user32, hwnd)
    if current is None or primary is None or insets is None:
        return None
    return user32, hwnd, current[0], current[1], primary[0], insets


def fit_maximize(window: Any) -> None:
    """Set ``MaximizedBounds`` for the monitor the window is on now."""
    try:
        placed = _placement(window)
        native = getattr(window, "native", None)
        if placed is None or native is None:
            return
        _, _, monitor, work, primary, insets = placed
        bounds = max_bounds(monitor, work, primary, insets)
        from System.Drawing import Rectangle

        wanted = Rectangle(bounds.x, bounds.y, bounds.w, bounds.h)
        if not native.MaximizedBounds.Equals(wanted):
            native.MaximizedBounds = wanted
    except Exception:
        log.debug("fit_maximize failed", exc_info=True)


def _placement_struct() -> Any:
    import ctypes
    from ctypes import wintypes

    class WINDOWPLACEMENT(ctypes.Structure):
        _fields_ = [
            ("length", wintypes.UINT),
            ("flags", wintypes.UINT),
            ("showCmd", wintypes.UINT),
            ("ptMinPosition", wintypes.POINT),
            ("ptMaxPosition", wintypes.POINT),
            ("rcNormalPosition", wintypes.RECT),
        ]

    placement = WINDOWPLACEMENT()
    placement.length = ctypes.sizeof(WINDOWPLACEMENT)
    return placement


def restore_window(window: Any) -> None:
    """Restore the window to the normal size Windows kept for it.

    WinForms restores a borderless form by its client size and does not know about the
    resize frame added afterwards, so every maximize and restore shrank the window by the
    frame (14 px). Windows' own placement still holds the right rect; put it back.
    """
    import ctypes

    hwnd = _hwnd(window)
    placement = None
    if hwnd:
        try:
            user32 = _user32()
            candidate = _placement_struct()
            if user32.GetWindowPlacement(hwnd, ctypes.byref(candidate)):
                placement = candidate
        except Exception:
            log.debug("GetWindowPlacement failed", exc_info=True)
    window.restore()
    if placement is None:
        return
    try:
        placement.showCmd = _SW_SHOWNORMAL
        _user32().SetWindowPlacement(hwnd, ctypes.byref(placement))
    except Exception:
        log.debug("SetWindowPlacement failed", exc_info=True)


def keep_off_taskbar(window: Any) -> None:
    """After a move or resize: refresh the bounds and pull a maximized window into the work area."""
    fit_maximize(window)
    try:
        placed = _placement(window)
        if placed is None:
            return
        user32, hwnd, _, work, _, insets = placed
        if not user32.IsZoomed(hwnd):
            return
        wanted = maximized_rect(work, insets)
        if _window_rect(user32, hwnd) != wanted:
            user32.SetWindowPos(
                hwnd, None, wanted.x, wanted.y, wanted.w, wanted.h, _SWP_NOZORDER | _SWP_NOACTIVATE
            )
    except Exception:
        log.debug("keep_off_taskbar failed", exc_info=True)
