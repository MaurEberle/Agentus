from __future__ import annotations

from app.help.chunk import chunk_markdown


def test_heading_sections() -> None:
    text = "# A\nhello\n# B\nworld"
    chunks = chunk_markdown(text, "doc", "hash")
    sections = [c.section for c in chunks]
    assert "A" in sections
    assert "B" in sections
    assert len(chunks) >= 2
