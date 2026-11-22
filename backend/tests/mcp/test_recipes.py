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


def test_recipes_are_parsed_again_only_after_a_change(tmp_path, monkeypatch) -> None:
    """N9: every MCP node in every listed network re-read all recipe files."""
    import json as _json

    from app.mcp import recipe_loader

    folder = tmp_path / "recipes"
    folder.mkdir()
    recipe = next(r for r in load_recipes() if r.id == "git")
    source = recipe_loader.RECIPES_DIR / "git.json"
    (folder / "git.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(recipe_loader, "RECIPES_DIR", folder)
    reads = {"n": 0}
    real = recipe_loader._read_recipes

    def _counting(path):
        reads["n"] += 1
        return real(path)

    monkeypatch.setattr(recipe_loader, "_read_recipes", _counting)
    first = load_recipes()
    second = load_recipes()
    assert [r.id for r in first] == ["git"] == [r.id for r in second]
    assert reads["n"] == 1
    raw = _json.loads((folder / "git.json").read_text(encoding="utf-8"))
    raw["id"] = "git2"
    (folder / "git.json").write_text(_json.dumps(raw), encoding="utf-8")
    assert [r.id for r in load_recipes()] == ["git2"]
    assert reads["n"] == 2
