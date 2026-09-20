from __future__ import annotations

from pathlib import Path

from app.host.native_frame import (
    DRAG_REGION_SELECTOR,
    FRAME_STYLE,
    WS_MAXIMIZEBOX,
    WS_THICKFRAME,
    configure_webview,
    enable_frameless_resize,
    resolve_app_icon,
    set_window_icon,
)


class _Settings:
    def __init__(self) -> None:
        self.data = {"DRAG_REGION_SELECTOR": ".pywebview-drag-region"}

    def __setitem__(self, key: str, value: str) -> None:
        self.data[key] = value

    def __getitem__(self, key: str) -> str:
        return self.data[key]


def test_configure_webview_uses_app_drag() -> None:
    mod = type("W", (), {"settings": _Settings()})()
    configure_webview(mod)
    assert mod.settings["DRAG_REGION_SELECTOR"] == DRAG_REGION_SELECTOR
    assert DRAG_REGION_SELECTOR == ".app-drag"


def test_frame_style_includes_resize_and_max() -> None:
    assert FRAME_STYLE & WS_THICKFRAME
    assert FRAME_STYLE & WS_MAXIMIZEBOX


def test_enable_frameless_resize_without_native() -> None:
    enable_frameless_resize(object())


def test_resolve_app_icon_dev() -> None:
    path = resolve_app_icon()
    assert path is not None
    ico = Path(path)
    assert ico.is_file()
    assert ico.name == "app.ico"
    assert ico.stat().st_size > 1000


def test_set_window_icon_without_native() -> None:
    set_window_icon(object(), resolve_app_icon())


def test_ico_has_small_sizes() -> None:
    import struct

    data = Path(resolve_app_icon() or "").read_bytes()
    _reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert kind == 1
    assert count >= 4
    sizes = []
    for i in range(count):
        w, h = struct.unpack_from("<BB", data, 6 + 16 * i)
        sizes.append(w or 256)
    assert 16 in sizes
    assert 32 in sizes
    assert 256 in sizes
