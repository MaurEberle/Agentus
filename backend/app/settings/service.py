"""Settings, credentials, session, data-location. No SQL, no secrets in responses."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.common.types import ServiceStatus
from app.db.bootstrap import get_data_location as db_get_data_location
from app.db.bootstrap import set_data_dir as db_set_data_dir
from app.db.credentials import (
    delete_credential_meta,
    get_credential,
    insert_credential,
    list_credentials,
    update_credential_meta,
)
from app.db.errors import NotFound
from app.db.networks import get_network
from app.db.paths import is_invalid_data_dir
from app.db.settings import get_settings as db_get_settings
from app.db.settings import put_settings as db_put_settings
from app.db.vault import delete as vault_delete
from app.db.vault import put as vault_put
from app.http.errors import AppError
from app.settings.defaults import default_settings
from app.settings.in_use import is_in_use, usage_labels
from app.settings.models import (
    AppSettings,
    AppSettingsPatch,
    CredentialCreate,
    CredentialListItem,
    CredentialPatch,
    DataLocation,
    DataLocationPost,
    HelpChatSettings,
    SessionOut,
)
from app.settings.urls import normalize_ollama_base_url, normalize_optional_http_url

_RETENTION = {30, 90, 365, None}

_HELP_CHAT_KEYS = {
    "provider": "provider",
    "model": "model",
    "credentialId": "credentialId",
    "credential_id": "credentialId",
    "embeddingProvider": "embeddingProvider",
    "embedding_provider": "embeddingProvider",
    "embeddingModel": "embeddingModel",
    "embedding_model": "embeddingModel",
    "embeddingCredentialId": "embeddingCredentialId",
    "embedding_credential_id": "embeddingCredentialId",
    "webSearchEnabled": "webSearchEnabled",
    "web_search_enabled": "webSearchEnabled",
    "webSearchCredentialId": "webSearchCredentialId",
    "web_search_credential_id": "webSearchCredentialId",
    "fallbackModel": "fallbackModel",
    "fallback_model": "fallbackModel",
}


@dataclass(frozen=True)
class RunSlice:
    service_status: ServiceStatus = "stopped"
    run_id: str | None = None
    started_at: str | None = None


_run_slice_provider: Callable[[], RunSlice] | None = None


def set_run_slice_provider(fn: Callable[[], RunSlice] | None) -> None:
    global _run_slice_provider
    _run_slice_provider = fn


def reset_run_slice_provider() -> None:
    set_run_slice_provider(None)


def current_run_slice() -> RunSlice:
    if _run_slice_provider is None:
        return RunSlice()
    return _run_slice_provider()


def is_run_busy() -> bool:
    return current_run_slice().service_status in ("starting", "running", "stopping")


def mask_from_secret(secret: str) -> str:
    stripped = secret.strip()
    if len(stripped) < 4:
        return "***"
    return "…" + stripped[-4:]


def _persist(settings: AppSettings) -> None:
    db_put_settings(settings.model_dump(by_alias=True, mode="json"))


def _merge_help_chat(current: HelpChatSettings, patch: dict[str, Any]) -> HelpChatSettings:
    data = current.model_dump(by_alias=True)
    for key, value in patch.items():
        alias = _HELP_CHAT_KEYS.get(key)
        if alias is None:
            continue
        data[alias] = value
    return HelpChatSettings.model_validate(data)


def load_settings() -> AppSettings:
    raw = db_get_settings()
    if not raw:
        settings = default_settings()
        _persist(settings)
        return settings
    defaults = default_settings().model_dump(by_alias=True)
    help_raw = raw.get("helpChat") if isinstance(raw.get("helpChat"), dict) else {}
    merged_help = {**defaults["helpChat"], **help_raw}
    merged = {**defaults, **raw, "helpChat": merged_help}
    settings = AppSettings.model_validate(merged)
    if settings.history_retention_days not in _RETENTION:
        settings = settings.model_copy(update={"history_retention_days": 90})
    return settings


def patch_settings(body: AppSettingsPatch) -> AppSettings:
    current = load_settings()
    updates: dict[str, Any] = {}
    if body.ollama_base_url is not None:
        try:
            updates["ollama_base_url"] = normalize_ollama_base_url(body.ollama_base_url)
        except ValueError:
            raise AppError("settings.ollamaUrl.invalid", status_code=400) from None
    if "openai_compat_base_url" in body.model_fields_set:
        try:
            updates["openai_compat_base_url"] = normalize_optional_http_url(
                body.openai_compat_base_url
            )
        except ValueError:
            raise AppError("settings.ollamaUrl.invalid", status_code=400) from None
    if body.help_chat_fab_visible is not None:
        updates["help_chat_fab_visible"] = body.help_chat_fab_visible
    if body.help_chat is not None:
        updates["help_chat"] = _merge_help_chat(current.help_chat, body.help_chat)
    if "active_network_id" in body.model_fields_set:
        updates["active_network_id"] = body.active_network_id
    if "history_retention_days" in body.model_fields_set:
        if body.history_retention_days not in _RETENTION:
            raise AppError("settings.retention.invalid", status_code=400)
        updates["history_retention_days"] = body.history_retention_days
    if body.chat_onboarding_seen is not None:
        updates["chat_onboarding_seen"] = body.chat_onboarding_seen
    settings = current.model_copy(update=updates)
    _persist(settings)
    return settings


def _credential_item(row: dict[str, Any]) -> CredentialListItem:
    return CredentialListItem(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        mask=row["mask"],
        in_use=is_in_use(row["id"]),
    )


def list_credential_items() -> list[CredentialListItem]:
    return [_credential_item(row) for row in list_credentials()]


def create_credential(body: CredentialCreate) -> CredentialListItem:
    secret = body.secret.strip()
    if not secret:
        raise AppError("credentials.secret.required", status_code=400)
    cred_id = str(uuid.uuid4())
    mask = mask_from_secret(secret)
    vault_put(cred_id, secret)
    try:
        insert_credential(cred_id, body.name, body.kind, mask)
    except Exception:
        vault_delete(cred_id)
        raise
    row = get_credential(cred_id)
    assert row is not None
    return _credential_item(row)


def patch_credential(cred_id: str, body: CredentialPatch) -> CredentialListItem:
    existing = get_credential(cred_id)
    if existing is None:
        raise AppError("credentials.notFound", status_code=404)
    mask: str | None = None
    if body.secret is not None and body.secret != "":
        secret = body.secret.strip()
        if not secret:
            raise AppError("credentials.secret.required", status_code=400)
        vault_put(cred_id, secret)
        mask = mask_from_secret(secret)
    try:
        update_credential_meta(cred_id, name=body.name, kind=body.kind, mask=mask)
    except NotFound:
        raise AppError("credentials.notFound", status_code=404) from None
    row = get_credential(cred_id)
    assert row is not None
    return _credential_item(row)


def delete_credential(cred_id: str) -> None:
    existing = get_credential(cred_id)
    if existing is None:
        raise AppError("credentials.notFound", status_code=404)
    labels = usage_labels(cred_id)
    if labels:
        raise AppError(
            "credentials.inUse",
            status_code=409,
            message=", ".join(labels),
        )
    try:
        vault_delete(cred_id)
    except Exception:
        pass
    try:
        delete_credential_meta(cred_id)
    except NotFound:
        raise AppError("credentials.notFound", status_code=404) from None


def _session_from(settings: AppSettings) -> SessionOut:
    slice_ = current_run_slice()
    name: str | None = None
    if settings.active_network_id:
        row = get_network(settings.active_network_id)
        if row is not None:
            name = row.name
    return SessionOut(
        active_network_id=settings.active_network_id,
        active_network_name=name,
        service_status=slice_.service_status,
        run_id=slice_.run_id,
        started_at=slice_.started_at,
    )


def get_session() -> SessionOut:
    return _session_from(load_settings())


def set_active_network(network_id: str | None) -> SessionOut:
    if network_id is not None:
        row = get_network(network_id)
        if row is None:
            raise AppError("networks.notFound", status_code=404)
    settings = load_settings().model_copy(update={"active_network_id": network_id})
    _persist(settings)
    return _session_from(settings)


def get_location() -> DataLocation:
    return DataLocation.model_validate(db_get_data_location())


def post_location(body: DataLocationPost) -> DataLocation:
    if is_run_busy():
        raise AppError("dataDir.busy", status_code=409)
    current = db_get_data_location()
    if current.get("readOnly"):
        raise AppError("dataDir.readOnly", status_code=400)
    try:
        resolved = Path(body.path).expanduser().resolve()
    except (OSError, RuntimeError):
        raise AppError("dataDir.invalidPath", status_code=400) from None
    if is_invalid_data_dir(resolved):
        raise AppError("dataDir.invalidPath", status_code=400)
    return DataLocation.model_validate(db_set_data_dir(resolved, copy=body.copy_files))


def dump_session(session: SessionOut) -> dict[str, Any]:
    data = session.model_dump(by_alias=True)
    for key in ("activeNetworkName", "runId", "startedAt"):
        if data.get(key) is None:
            data.pop(key, None)
    return data
