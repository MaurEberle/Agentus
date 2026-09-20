from __future__ import annotations

from app.db.bootstrap import WindowGeom
from app.host.geometry import (
    MIN_H,
    MIN_W,
    RATIO_FULL,
    RATIO_LARGE,
    RATIO_MEDIUM,
    Rect,
    clamp_to_visible,
    default_rect,
    from_bootstrap,
    size_ratio,
    start_placement,
)


def _patch_display(monkeypatch, monitor: Rect, work: Rect | None = None) -> None:
    work = work or monitor

    def _display() -> tuple[Rect, Rect]:
        return monitor, work

    monkeypatch.setattr("app.host.geometry.display", _display)


def test_fhd_is_medium_75_percent(monkeypatch) -> None:
    monitor = Rect(0, 0, 1920, 1080)
    work = Rect(0, 0, 1920, 1040)
    _patch_display(monkeypatch, monitor, work)
    rect, maximized = start_placement()
    assert size_ratio(monitor) == RATIO_MEDIUM
    assert maximized is False
    assert rect.w == int(1920 * RATIO_MEDIUM)
    assert rect.h == int(1080 * RATIO_MEDIUM)
    assert rect.x == work.x + (work.w - rect.w) // 2
    assert rect.y == work.y + (work.h - rect.h) // 2


def test_4k_is_large_65_percent(monkeypatch) -> None:
    monitor = Rect(0, 0, 3840, 2160)
    _patch_display(monkeypatch, monitor)
    rect, maximized = start_placement()
    assert size_ratio(monitor) == RATIO_LARGE
    assert maximized is False
    assert rect.w == int(3840 * RATIO_LARGE)
    assert rect.h == int(2160 * RATIO_LARGE)
    assert rect.x == (3840 - rect.w) // 2
    assert rect.y == (2160 - rect.h) // 2


def test_qhd_is_large_65_percent(monkeypatch) -> None:
    monitor = Rect(0, 0, 2560, 1440)
    work = Rect(0, 0, 2560, 1400)
    _patch_display(monkeypatch, monitor, work)
    rect, maximized = start_placement()
    assert size_ratio(monitor) == RATIO_LARGE
    assert maximized is False
    assert rect.w == int(2560 * RATIO_LARGE)
    assert rect.h == int(1440 * RATIO_LARGE)
    assert rect.w == 1664
    assert rect.h == 936


def test_small_laptop_is_fullscreen(monkeypatch) -> None:
    monitor = Rect(0, 0, 1366, 768)
    _patch_display(monkeypatch, monitor)
    assert size_ratio(monitor) == RATIO_FULL
    rect, maximized = start_placement()
    assert maximized is True
    assert rect.w >= MIN_W
    assert rect.h >= MIN_H


def test_from_bootstrap_uses_start_placement(monkeypatch) -> None:
    _patch_display(monkeypatch, Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040))
    rect = from_bootstrap(WindowGeom(x=10, y=10, w=1280, h=720))
    expected = default_rect()
    assert rect == expected
    assert rect == start_placement()[0]


def test_clamp_far_offscreen_resets(monkeypatch) -> None:
    _patch_display(monkeypatch, Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040))
    rect = clamp_to_visible(Rect(x=-9000, y=0, w=800, h=600))
    assert 0 <= rect.x < 1920
    assert rect.w >= MIN_W
    assert rect.h >= MIN_H


def test_clamp_tiny_width(monkeypatch) -> None:
    _patch_display(monkeypatch, Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040))
    rect = clamp_to_visible(Rect(x=100, y=100, w=100, h=100))
    assert rect.w >= MIN_W
    assert rect.h >= MIN_H


def test_degenerate_work_area_does_not_recurse(monkeypatch) -> None:
    _patch_display(monkeypatch, Rect(0, 0, 0, 0), Rect(0, 0, 0, 0))
    rect = default_rect()
    assert rect.w >= MIN_W
    assert rect.h >= MIN_H
    off = clamp_to_visible(Rect(x=-9000, y=-9000, w=800, h=600))
    assert off.w >= MIN_W
    assert off.h >= MIN_H


def test_tiny_work_area_does_not_recurse(monkeypatch) -> None:
    _patch_display(monkeypatch, Rect(0, 0, 10, 10), Rect(0, 0, 10, 10))
    rect = default_rect()
    assert rect.w >= MIN_W
    assert rect.h >= MIN_H
    assert rect.x == 0
    assert rect.y == 0
