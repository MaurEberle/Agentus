"""Settings domain. Routers import these; they do not talk to sqlite."""

from app.settings.defaults import DEFAULT_OLLAMA_BASE_URL, default_settings
from app.settings.in_use import (
    is_in_use,
    set_mcp_usage_provider,
    usage_labels,
)
from app.settings.service import (
    RunSlice,
    create_credential,
    current_run_slice,
    delete_credential,
    dump_session,
    get_location,
    get_session,
    is_run_busy,
    list_credential_items,
    load_settings,
    mask_from_secret,
    patch_credential,
    patch_settings,
    post_location,
    set_active_network,
    set_run_slice_provider,
)

__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
    "RunSlice",
    "create_credential",
    "current_run_slice",
    "default_settings",
    "delete_credential",
    "dump_session",
    "get_location",
    "get_session",
    "is_in_use",
    "is_run_busy",
    "list_credential_items",
    "load_settings",
    "mask_from_secret",
    "patch_credential",
    "patch_settings",
    "post_location",
    "set_active_network",
    "set_mcp_usage_provider",
    "set_run_slice_provider",
    "usage_labels",
]
