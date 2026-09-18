"""In-app help chat. Independent of the agent run; no MCP."""

from app.help.status import get_degraded, get_status, set_degraded

__all__ = ["get_degraded", "get_status", "set_degraded"]
