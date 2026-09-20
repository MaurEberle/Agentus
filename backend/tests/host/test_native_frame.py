from __future__ import annotations

from app.host.native_frame import (
    DRAG_REGION_SELECTOR,
    FRAME_STYLE,
    WS_MAXIMIZEBOX,
    WS_THICKFRAME,
    configure_webview,
    enable_frameless_resize,
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
