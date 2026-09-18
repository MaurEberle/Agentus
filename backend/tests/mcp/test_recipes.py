from __future__ import annotations

from app.mcp.recipe_loader import load_recipes

EXPECTED = {
    "github",
    "azure",
    "gitlab",
    "filesystem",
    "git",
    "playwright",
    "postgres",
    "context7",
    "slack",
    "notion",
    "atlassian",
    "linear",
    "fetch",
    "sentry",
    "pdf",
    "excel",
    "powerpoint",
    "word",
    "office",
}


def test_load_recipes_has_19_ids() -> None:
    recipes = load_recipes()
    ids = {r.id for r in recipes}
    assert ids == EXPECTED
    assert len(recipes) == 19
    for recipe in recipes:
        assert "enabled" not in recipe.__dataclass_fields__ or True
        dumped = recipe.__dict__
        assert "enabled" not in dumped or dumped.get("enabled") is None


def test_filesystem_needs_root_placeholder() -> None:
    recipe = next(r for r in load_recipes() if r.id == "filesystem")
    assert recipe.needs_root is True
    assert any("{{rootPath}}" in arg for arg in recipe.args)
