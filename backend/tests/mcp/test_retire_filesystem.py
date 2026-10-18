from __future__ import annotations

from app.db import init
from app.db.engine import utc_now
from app.db.networks import NetworkRow, get_network, upsert_network
from app.db.settings import get_mcp_server, put_mcp_server
from app.mcp.retire_filesystem import retire_filesystem_mcp


def test_filesystem_mcp_node_becomes_file_access(api_env) -> None:
    init()
    put_mcp_server(
        "srv-fs",
        {
            "id": "srv-fs",
            "recipe_id": "filesystem",
            "name": "Dateisystem",
            "enabled": True,
            "transport": "stdio",
        },
    )
    upsert_network(
        NetworkRow(
            id="net-1",
            name="Coder",
            description=None,
            tags=[],
            document={
                "id": "net-1",
                "nodes": [
                    {
                        "id": "mcp-1",
                        "type": "mcp",
                        "position": {"x": 0, "y": 0},
                        "data": {
                            "displayName": "Dateisystem",
                            "mcpServerId": "srv-fs",
                            "rootPath": "C:/work/app",
                        },
                    }
                ],
                "edges": [],
            },
            updated_at=utc_now(),
            last_used_at=None,
            last_run_id=None,
        )
    )
    assert retire_filesystem_mcp() == 1
    stored = get_network("net-1")
    assert stored is not None
    node = stored.document["nodes"][0]
    assert node["type"] == "tool"
    assert node["data"]["kind"] == "file_access"
    assert node["data"]["rootPath"] == "C:/work/app"
    assert node["data"]["displayName"] == "Dateisystem"
    assert get_mcp_server("srv-fs") is None
    assert retire_filesystem_mcp() == 0
