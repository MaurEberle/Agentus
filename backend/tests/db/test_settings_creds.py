from __future__ import annotations

import pytest

from app.db import init
from app.db.credentials import (
    delete_credential_meta,
    get_credential,
    insert_credential,
    list_credentials,
    update_credential_meta,
)
from app.db.errors import NotFound
from app.db.settings import (
    delete_mcp_server,
    get_mcp_server,
    get_settings,
    list_mcp_servers,
    put_mcp_server,
    put_settings,
)
from app.db.vault import get as vault_get
from app.db.vault import put as vault_put


def test_settings_camel_case_roundtrip() -> None:
    init()
    assert get_settings() is None
    payload = {
        "ollamaBaseUrl": "http://127.0.0.1:11434",
        "helpChat": {"provider": "ollama", "model": "llama3.2:1b"},
        "historyRetentionDays": 90,
    }
    put_settings(payload)
    assert get_settings() == payload


def test_credentials_list_has_no_secret() -> None:
    init()
    insert_credential("c1", "xAI", "xai", "…abcd")
    vault_put("c1", "real-secret")
    items = list_credentials()
    assert len(items) == 1
    assert "secret" not in items[0]
    assert items[0]["mask"] == "…abcd"
    assert items[0]["kind"] == "xai"
    assert vault_get("c1") == "real-secret"
    update_credential_meta("c1", name="xAI cloud")
    assert get_credential("c1")["name"] == "xAI cloud"
    delete_credential_meta("c1")
    assert get_credential("c1") is None
    with pytest.raises(NotFound):
        delete_credential_meta("c1")


def test_mcp_servers_payload() -> None:
    init()
    put_mcp_server("mcp-1", {"name": "files", "enabled": True})
    listed = list_mcp_servers()
    assert listed == [{"name": "files", "enabled": True, "id": "mcp-1"}]
    assert get_mcp_server("mcp-1")["name"] == "files"
    delete_mcp_server("mcp-1")
    assert list_mcp_servers() == []
