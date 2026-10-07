from __future__ import annotations

from app.run.wait_ask import excerpt


def test_excerpt_keeps_short_text() -> None:
    assert excerpt("Welche Sprache?") == "Welche Sprache?"


def test_excerpt_collapses_whitespace_and_clips() -> None:
    text = "  " + ("wort " * 40)
    clipped = excerpt(text, limit=20)
    assert "\n" not in clipped
    assert clipped.endswith("…")
    assert len(clipped) <= 20
