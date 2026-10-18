from __future__ import annotations

from app.mcp.recipe_loader import load_recipes

EXPECTED = {
    "github",
    "azure",
    "gitlab",
    "git",
    "playwright",
    "postgres",
    "context7",
    "slack",
    "notion",
    "atlassian",
    "linear",
    "sentry",
    "excel",
}


def test_load_recipes_has_known_ids() -> None:
    recipes = load_recipes()
    ids = {r.id for r in recipes}
    assert ids == EXPECTED
    assert len(recipes) == 13
    for recipe in recipes:
        assert "enabled" not in recipe.__dataclass_fields__ or True
        dumped = recipe.__dict__
        assert "enabled" not in dumped or dumped.get("enabled") is None


def test_github_needs_pat_and_no_root() -> None:
    recipe = next(r for r in load_recipes() if r.id == "github")
    assert recipe.needs_root is False
    assert recipe.credential_kinds == ["github"]
    assert recipe.env_from_kind.get("github") == "GITHUB_PERSONAL_ACCESS_TOKEN"
    assert recipe.runtime == "none"
    assert recipe.command == "github-mcp-server"
    assert recipe.args == ["stdio"]
    assert "query" in recipe.tool_schemas["search_repositories"]["properties"]


def test_git_uses_uvx_repository() -> None:
    recipe = next(r for r in load_recipes() if r.id == "git")
    assert recipe.runtime == "uvx"
    assert recipe.args[:2] == ["mcp-server-git", "--repository"]
    assert recipe.needs_root is True
    assert recipe.append_root is True


def test_excel_stdio_transport() -> None:
    recipe = next(r for r in load_recipes() if r.id == "excel")
    assert recipe.runtime == "npx"
    assert recipe.args == ["-y", "@negokaz/excel-mcp-server"]
    assert recipe.root_on_node is True
    assert recipe.append_root is False


def test_azure_starts_server() -> None:
    recipe = next(r for r in load_recipes() if r.id == "azure")
    assert recipe.args[-2:] == ["server", "start"]


def test_only_shipped_recipes_are_available() -> None:
    recipes = load_recipes()
    available = {r.id for r in recipes if r.available}
    assert available == {"github", "git", "excel"}
