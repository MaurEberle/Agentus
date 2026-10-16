from __future__ import annotations

from urllib.parse import urlparse

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_guarded_ids: set[int] = set()


def is_allowed_url(url: str, port: int) -> bool:
    if url in {"about:blank", "about:blank/"}:
        return True
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if host not in _LOOPBACK_HOSTS:
        return False
    explicit = parsed.port
    if explicit is None or explicit == -1:
        explicit = 443 if parsed.scheme == "https" else 80
    return explicit == port


def open_external_url(url: str) -> bool:
    """Open http(s) in the system browser. Other schemes stay closed."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    import webbrowser

    return bool(webbrowser.open(parsed.geturl()))


def event_url(args: object) -> str:
    uri = getattr(args, "Uri", None)
    if uri is None:
        getter = getattr(args, "get_Uri", None)
        if callable(getter):
            uri = getter()
    return str(uri or "")


def cancel_navigation(args: object) -> None:
    if hasattr(args, "Cancel"):
        try:
            args.Cancel = True
            return
        except Exception:
            pass
    setter = getattr(args, "set_Cancel", None)
    if callable(setter):
        setter(True)


def attach_navigation_guard(control: object, port: int) -> None:
    def on_start(_sender: object, args: object) -> None:
        if not is_allowed_url(event_url(args), port):
            cancel_navigation(args)

    control.NavigationStarting += on_start  # type: ignore[attr-defined]


def webview_control(window: object) -> object | None:
    native = getattr(window, "native", None)
    if native is None:
        return None
    browser = getattr(native, "browser", None)
    candidates = (
        getattr(native, "webview", None),
        getattr(browser, "webview", None) if browser is not None else None,
    )
    for candidate in candidates:
        if candidate is not None and hasattr(candidate, "NavigationStarting"):
            return candidate
    return None


def reset_navigation_guard() -> None:
    _guarded_ids.clear()


def guard_navigation(window: object, port: int) -> bool:
    """Cancel WebView2 navigations that leave the app origin. Safe to call twice."""
    control = webview_control(window)
    if control is None:
        return False
    key = id(control)
    if key in _guarded_ids:
        return True
    attach_navigation_guard(control, port)
    _guarded_ids.add(key)
    return True
