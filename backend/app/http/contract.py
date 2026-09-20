"""HTTP v1 contract from python_backend_api.md.

Not a domain module. Routers implement these paths; they do not invent extras.
``offen (nach Bau)`` is omitted on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass

# Router module that owns the path once that coding prompt lands.
# All v1 owners are live after python_backend_run.md.

META = "meta"
SESSION = "session"
SETTINGS = "settings"
CREDENTIALS = "credentials"
DATA_LOCATION = "data_location"
RUNTIME = "runtime"
RUN = "run"
NETWORKS = "networks"
MCP = "mcp"
TOOLS = "tools"
HELP_CHAT = "help_chat"
RUNS = "runs"


@dataclass(frozen=True)
class ContractRoute:
    method: str
    path: str
    owner: str


ROUTES: tuple[ContractRoute, ...] = (
    ContractRoute("GET", "/api/health", META),
    ContractRoute("GET", "/api/about", META),
    ContractRoute("GET", "/api/session", SESSION),
    ContractRoute("PUT", "/api/session/active-network", SESSION),
    ContractRoute("POST", "/api/run/start", RUN),
    ContractRoute("POST", "/api/run/stop", RUN),
    ContractRoute("GET", "/api/run", RUN),
    ContractRoute("GET", "/api/run/stream", RUN),
    ContractRoute("POST", "/api/run/chat", RUN),
    ContractRoute("POST", "/api/run/chat/abort", RUN),
    ContractRoute("GET", "/api/networks", NETWORKS),
    ContractRoute("GET", "/api/networks/:id", NETWORKS),
    ContractRoute("POST", "/api/networks", NETWORKS),
    ContractRoute("PUT", "/api/networks/:id", NETWORKS),
    ContractRoute("PATCH", "/api/networks/:id", NETWORKS),
    ContractRoute("POST", "/api/networks/tags", NETWORKS),
    ContractRoute("DELETE", "/api/networks/:id", NETWORKS),
    ContractRoute("DELETE", "/api/networks", NETWORKS),
    ContractRoute("POST", "/api/networks/:id/duplicate", NETWORKS),
    ContractRoute("POST", "/api/networks/:id/validate", NETWORKS),
    ContractRoute("GET", "/api/networks/:id/export", NETWORKS),
    ContractRoute("POST", "/api/networks/import", NETWORKS),
    ContractRoute("POST", "/api/networks/:id/knowledge/:nodeId/reindex", NETWORKS),
    ContractRoute("GET", "/api/settings", SETTINGS),
    ContractRoute("PATCH", "/api/settings", SETTINGS),
    ContractRoute("GET", "/api/data-location", DATA_LOCATION),
    ContractRoute("POST", "/api/data-location", DATA_LOCATION),
    ContractRoute("GET", "/api/credentials", CREDENTIALS),
    ContractRoute("POST", "/api/credentials", CREDENTIALS),
    ContractRoute("PATCH", "/api/credentials/:id", CREDENTIALS),
    ContractRoute("DELETE", "/api/credentials/:id", CREDENTIALS),
    ContractRoute("POST", "/api/runtime/ping", RUNTIME),
    ContractRoute("GET", "/api/runtime/models", RUNTIME),
    ContractRoute("POST", "/api/runtime/test-llm", RUNTIME),
    ContractRoute("GET", "/api/mcp/recipes", MCP),
    ContractRoute("GET", "/api/mcp/servers", MCP),
    ContractRoute("POST", "/api/mcp/servers", MCP),
    ContractRoute("PATCH", "/api/mcp/servers/:id", MCP),
    ContractRoute("POST", "/api/mcp/servers/:id/enabled", MCP),
    ContractRoute("POST", "/api/mcp/servers/:id/ping", MCP),
    ContractRoute("DELETE", "/api/mcp/servers/:id", MCP),
    ContractRoute("GET", "/api/tools/catalog", TOOLS),
    ContractRoute("GET", "/api/help-chat/status", HELP_CHAT),
    ContractRoute("POST", "/api/help-chat/ping", HELP_CHAT),
    ContractRoute("GET", "/api/help-chat/messages", HELP_CHAT),
    ContractRoute("POST", "/api/help-chat/messages", HELP_CHAT),
    ContractRoute("POST", "/api/help-chat/abort", HELP_CHAT),
    ContractRoute("POST", "/api/help-chat/clear", HELP_CHAT),
    ContractRoute("POST", "/api/help-chat/reindex", HELP_CHAT),
    ContractRoute("GET", "/api/runs", RUNS),
    ContractRoute("GET", "/api/runs/calls", RUNS),
    ContractRoute("GET", "/api/runs/:id", RUNS),
    ContractRoute("GET", "/api/runs/:id/logs", RUNS),
    ContractRoute("DELETE", "/api/runs", RUNS),
    ContractRoute("POST", "/api/runs/purge", RUNS),
)

# include_all module → owner tag
OWNER_BY_MODULE = {
    "app.http.routers.meta": META,
    "app.http.routers.settings": SETTINGS,
    "app.http.routers.credentials": CREDENTIALS,
    "app.http.routers.data_location": DATA_LOCATION,
    "app.http.routers.session": SESSION,
    "app.http.routers.runtime": RUNTIME,
    "app.http.routers.tools": TOOLS,
    "app.http.routers.mcp": MCP,
    "app.http.routers.networks": NETWORKS,
    "app.http.routers.run": RUN,
    "app.http.routers.runs": RUNS,
    "app.http.routers.help_chat": HELP_CHAT,
}

STORE_IDS = frozenset({"settings", "help", "workspace", "history"})
SERVICE_STATUSES = frozenset(
    {"disconnected", "stopped", "starting", "running", "stopping", "error"}
)
PROVIDERS = frozenset({"ollama", "xai", "openai", "anthropic", "gemini", "openai_compat"})
ERROR_KEYS_400 = frozenset({"http.validation"})
NOT_FOUND_KEY = "http.notFound"


def normalize_path(path: str) -> str:
    """``/api/credentials/{credential_id}`` and ``/api/credentials/:id`` → same shape."""
    out: list[str] = []
    for part in path.strip("/").split("/"):
        if part.startswith("{") and part.endswith("}"):
            out.append(":p")
        elif part.startswith(":"):
            out.append(":p")
        else:
            out.append(part)
    return "/" + "/".join(out)


def route_key(method: str, path: str) -> tuple[str, str]:
    return method.upper(), normalize_path(path)
