"""MCP attachment. Help must not import this package."""

from app.mcp.catalog import mcp_catalog_groups, mcp_usage_labels
from app.mcp.sessions import SESSIONS


def register_hooks() -> None:
    from app.settings.in_use import set_mcp_usage_provider
    from app.tools.catalog import set_mcp_catalog_provider

    set_mcp_catalog_provider(mcp_catalog_groups)
    set_mcp_usage_provider(mcp_usage_labels)


__all__ = ["SESSIONS", "register_hooks"]
