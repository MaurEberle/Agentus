"""Help-doc locale folders under resources/help_docs."""

from __future__ import annotations

from pathlib import Path

HELP_DOC_LOCALES = ("de", "en", "es", "fr", "tr", "pt", "zh", "ja", "ar")


def resolve_help_locale(value: str | None) -> str:
    base = (value or "de").split("-")[0].lower()
    return base if base in HELP_DOC_LOCALES else "de"


def locale_from_corpus_path(path: Path, root: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    first = rel.parts[0] if rel.parts else ""
    return first if first in HELP_DOC_LOCALES else None
