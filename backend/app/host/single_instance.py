from __future__ import annotations

import sys

MUTEX_NAME = "Local\\AgentusNetworkDesktopMutex"
WINDOW_TITLE = "Agentus Network"

_handle = None


def acquire() -> bool:
    if sys.platform != "win32":
        return True
    import ctypes

    global _handle
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    already = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    if already:
        if handle:
            kernel32.CloseHandle(handle)
        try_focus_existing()
        return False
    _handle = handle
    return True


def try_focus_existing() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if not hwnd:
            return
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        return


def release() -> None:
    global _handle
    if _handle is None or sys.platform != "win32":
        _handle = None
        return
    try:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(_handle)
    except Exception:
        pass
    _handle = None
