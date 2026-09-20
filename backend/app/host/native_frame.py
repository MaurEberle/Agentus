from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger("agentus.host")

DRAG_REGION_SELECTOR = ".app-drag"

GWL_STYLE = -16
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_THICKFRAME = 0x00040000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

FRAME_STYLE = WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010


def resolve_app_icon() -> str | None:
    """ICO next to the freeze, under _MEIPASS, or the repo resource in dev."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        exe_dir = Path(sys.executable).resolve().parent
        if meipass:
            candidates.append(Path(meipass) / "app.ico")
        candidates.append(exe_dir / "app.ico")
        candidates.append(exe_dir / "_internal" / "app.ico")
    else:
        candidates.append(
            Path(__file__).resolve().parents[3] / "resources" / "icons" / "app.ico"
        )
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def configure_webview(mod: Any) -> None:
    """pywebview drags via CSS selector, not -webkit-app-region (WebView2 ignores that)."""
    mod.settings["DRAG_REGION_SELECTOR"] = DRAG_REGION_SELECTOR


def _hwnd(window: Any) -> int | None:
    native = getattr(window, "native", None)
    handle = getattr(native, "Handle", None) if native is not None else None
    if handle is None:
        return None
    if hasattr(handle, "ToInt64"):
        return int(handle.ToInt64())
    if hasattr(handle, "ToInt32"):
        return int(handle.ToInt32())
    return int(handle)


def enable_frameless_resize(window: Any) -> None:
    """FormBorderStyle.None drops the size grip; put WS_THICKFRAME back for edge resize."""
    hwnd = _hwnd(window)
    if not hwnd:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        long_ptr = ctypes.c_ssize_t
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = long_ptr
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, long_ptr]
        user32.SetWindowLongPtrW.restype = long_ptr
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
        style = int(user32.GetWindowLongPtrW(hwnd, GWL_STYLE))
        user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style | FRAME_STYLE)
        user32.SetWindowPos(
            hwnd,
            None,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
    except Exception:
        log.debug("enable_frameless_resize failed", exc_info=True)


def set_window_icon(window: Any, icon_path: str | None) -> None:
    """Set small+big icons on the WinForms HWND. No-op if native handle is missing."""
    if not icon_path:
        return
    hwnd = _hwnd(window)
    native = getattr(window, "native", None)
    if native is not None:
        try:
            from System.Drawing import Icon as WinIcon

            native.Icon = WinIcon(icon_path)
        except Exception:
            log.debug("form Icon assignment failed", exc_info=True)
    if not hwnd:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.SendMessageW.restype = ctypes.c_ssize_t
        small = user32.LoadImageW(None, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        big = user32.LoadImageW(None, icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        if small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
        if big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
    except Exception:
        log.debug("set_window_icon failed", exc_info=True)
