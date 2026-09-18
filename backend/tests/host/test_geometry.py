from __future__ import annotations

from app.db.bootstrap import WindowGeom
from app.host.geometry import MIN_H, MIN_W, Rect, clamp_to_visible, default_rect, from_bootstrap


def test_default_rect_margin(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.host.geometry.work_area", lambda: Rect(0, 0, 1920, 1040)
    )
    rect = default_rect()
    assert rect.w == 1872
    assert rect.h == 992
    assert rect.x == 24
    assert rect.y == 24


def test_from_bootstrap_zero_uses_default(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.host.geometry.work_area", lambda: Rect(0, 0, 1920, 1040)
    )
    rect = from_bootstrap(WindowGeom(x=10, y=10, w=0, h=0))
    assert rect.w >= MIN_W
    assert rect.h >= MIN_H


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
