from __future__ import annotations

from fastapi.testclient import TestClient

from app.http.app import create_app
from app.tools.catalog import list_catalog_groups, openai_tools_for_kinds


def test_list_catalog_groups_first_party_only() -> None:
    groups = list_catalog_groups()
    assert len(groups) == 1
    assert groups[0].id == "firstParty"
    names = [tool.name for tool in groups[0].tools]
    kinds = [tool.kind for tool in groups[0].tools]
    assert names == ["http", "web_search", "datetime", "calculator"]
    assert names == kinds


def test_catalog_json_aliases() -> None:
    dumped = list_catalog_groups()[0].tools[0].model_dump(by_alias=True)
    assert "jsonSchema" in dumped
    assert "credentialKind" in dumped
    assert "json_schema" not in dumped


def test_openai_tools_for_calculator() -> None:
    tools = openai_tools_for_kinds(["calculator"])
    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "calculator"
    assert tools[0]["function"]["parameters"]["required"] == ["expression"]


def test_http_catalog_route() -> None:
    response = TestClient(create_app()).get("/api/tools/catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["groups"][0]["id"] == "firstParty"
    assert len(body["groups"][0]["tools"]) == 4
    assert "jsonSchema" in body["groups"][0]["tools"][0]
