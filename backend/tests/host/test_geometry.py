from __future__ import annotations

from app.db.bootstrap import WindowGeom
from app.host.geometry import MIN_H, MIN_W, Rect, clamp_to_visible, default_rect, from_bootstrap


def test_default_rect_centered_and_tall(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.host.geometry.work_area", lambda: Rect(0, 0, 1920, 1040)
    )
    rect = default_rect()
    assert rect.w == int(1920 * 0.86)
    assert rect.h == int(1040 * 0.92)
    assert rect.h > 720
    assert rect.x == (1920 - rect.w) // 2
    assert rect.y == (1040 - rect.h) // 2


def test_from_bootstrap_uses_centered_default(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.host.geometry.work_area", lambda: Rect(0, 0, 1920, 1040)
    )
    rect = from_bootstrap(WindowGeom(x=10, y=10, w=1280, h=720))
    expected = default_rect()
    assert rect == expected
    assert rect.h > 720


def test_clamp_far_offscreen_resets(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.host.geometry.work_area", lambda: Rect(0, 0, 1920, 1040)
    )
    rect = clamp_to_visible(Rect(x=-9000, y=0, w=800, h=600))
    assert 0 <= rect.x < 1920
    assert rect.w >= MIN_W
    assert rect.h >= MIN_H


def test_clamp_tiny_width(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.host.geometry.work_area", lambda: Rect(0, 0, 1920, 1040)
    )
    rect = clamp_to_visible(Rect(x=100, y=100, w=100, h=100))
    assert rect.w >= MIN_W
    assert rect.h >= MIN_H


def test_degenerate_work_area_does_not_recurse(monkeypatch) -> None:
    monkeypatch.setattr("app.host.geometry.work_area", lambda: Rect(0, 0, 0, 0))
    rect = default_rect()
    assert rect.w >= MIN_W
    assert rect.h >= MIN_H
    off = clamp_to_visible(Rect(x=-9000, y=-9000, w=800, h=600))
    assert off.w >= MIN_W
    assert off.h >= MIN_H


def test_tiny_work_area_does_not_recurse(monkeypatch) -> None:
    monkeypatch.setattr("app.host.geometry.work_area", lambda: Rect(0, 0, 10, 10))
    rect = default_rect()
    assert rect.w >= MIN_W
    assert rect.h >= MIN_H
    assert rect.x == 0
    assert rect.y == 0
