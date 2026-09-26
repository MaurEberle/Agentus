from __future__ import annotations

from app.db import init
from app.http.errors import AppError
from app.mcp.models import McpServerCreate
from app.mcp.service import create_server, list_servers, set_enabled
import pytest


def test_fresh_db_has_no_enabled_servers(api_env) -> None:
    init()
    assert list_servers() == []


def test_create_github_disabled(api_env) -> None:
    init()
    item = create_server(McpServerCreate(recipe_id="github"))
    assert item.recipe_id == "github"
    assert item.enabled is False
    assert item.name == "github"
    listed = list_servers()
    assert len(listed) == 1
    assert listed[0].enabled is False


def test_filesystem_enable_without_root(api_env) -> None:
    init()
    item = create_server(McpServerCreate(recipe_id="filesystem"))
    with pytest.raises(AppError) as err:
        set_enabled(item.id, True)
    assert err.value.message_key == "mcp.root.required"


def test_github_enable_without_credential(api_env) -> None:
    init()
    item = create_server(McpServerCreate(recipe_id="github"))
    with pytest.raises(AppError) as err:
        set_enabled(item.id, True)
    assert err.value.message_key == "mcp.credential.required"


def test_github_disable_keeps_default_credential(api_env) -> None:
    init()
    item = create_server(
        McpServerCreate(recipe_id="github", credential_ids=["cred-1"], enabled=True)
    )
    assert item.enabled is True
    disabled = set_enabled(item.id, False)
    assert disabled.enabled is False
    assert disabled.credential_ids == ["cred-1"]
    listed = list_servers()
    assert listed[0].enabled is False


def test_custom_without_command_or_url(api_env) -> None:
    init()
    with pytest.raises(AppError) as err:
        create_server(McpServerCreate(name="x", transport="stdio"))
    assert err.value.message_key == "mcp.custom.invalid"
