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
    "excel",
}


def test_load_recipes_has_known_ids() -> None:
    recipes = load_recipes()
    ids = {r.id for r in recipes}
    assert ids == EXPECTED
    assert len(recipes) == 15
    for recipe in recipes:
        assert "enabled" not in recipe.__dataclass_fields__ or True
        dumped = recipe.__dict__
        assert "enabled" not in dumped or dumped.get("enabled") is None


def test_filesystem_needs_root_placeholder() -> None:
    recipe = next(r for r in load_recipes() if r.id == "filesystem")
    assert recipe.needs_root is True
    assert recipe.root_on_node is True
    assert any("{{rootPath}}" in arg for arg in recipe.args)
    assert recipe.tool_schemas["list_directory"]["required"] == ["path"]


def test_github_needs_pat_and_no_root() -> None:
    recipe = next(r for r in load_recipes() if r.id == "github")
    assert recipe.needs_root is False
    assert recipe.credential_kinds == ["github"]
    assert recipe.env_from_kind.get("github") == "GITHUB_PERSONAL_ACCESS_TOKEN"
    assert "query" in recipe.tool_schemas["search_repositories"]["properties"]


def test_fetch_needs_no_credentials() -> None:
    recipe = next(r for r in load_recipes() if r.id == "fetch")
    assert recipe.credential_kinds == []
    assert recipe.needs_root is False
    assert recipe.runtime == "uvx"
    assert recipe.command == "uvx"
    assert recipe.args == ["mcp-server-fetch"]


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
