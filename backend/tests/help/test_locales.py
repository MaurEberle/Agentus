from __future__ import annotations

from pathlib import Path

from app.help.locales import HELP_DOC_LOCALES, locale_from_corpus_path, resolve_help_locale


def test_resolve_help_locale() -> None:
    assert resolve_help_locale(None) == "de"
    assert resolve_help_locale("fr-FR") == "fr"
    assert resolve_help_locale("zz") == "de"


def test_locale_from_corpus_path(tmp_path: Path) -> None:
    root = tmp_path / "corpus"
    (root / "fr").mkdir(parents=True)
    path = root / "fr" / "00-user-guide.md"
    path.write_text("x", encoding="utf-8")
    assert locale_from_corpus_path(path, root) == "fr"
    extra = root / "notes.md"
    extra.write_text("y", encoding="utf-8")
    assert locale_from_corpus_path(extra, root) is None


def test_bundled_help_docs_cover_all_locales() -> None:
    root = Path(__file__).resolve().parents[3] / "resources" / "help_docs"
    expected = [
        "00-user-guide.md",
        "01-dashboard.md",
        "02-editor.md",
        "03-monitoring-history.md",
        "04-settings.md",
        "05-graph-terms.md",
    ]
    assert set(HELP_DOC_LOCALES) == {p.name for p in root.iterdir() if p.is_dir()}
    for locale in HELP_DOC_LOCALES:
        names = sorted(p.name for p in (root / locale).glob("*.md"))
        assert names == expected
