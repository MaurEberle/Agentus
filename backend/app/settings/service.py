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
from app.settings.in_use import usage_index, usage_labels
from app.settings.models import (
    AppSettings,
    AppSettingsPatch,
    CredentialCreate,
    CredentialListItem,
    CredentialPatch,
    DataLocation,
    DataLocationPost,
    ArchitectSettings,
    HelpChatSettings,
    SessionOut,
    SessionWaitAsk,
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
    "webSearchProvider": "webSearchProvider",
    "web_search_provider": "webSearchProvider",
    "webSearchBaseUrl": "webSearchBaseUrl",
    "web_search_base_url": "webSearchBaseUrl",
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
    phase: str | None = None
    phase_label: str | None = None
    wait_ask: dict[str, Any] | None = None


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


_ARCHITECT_LIMITS = {
    "toolCallsPerAnswer": (5, 100),
    "webSearchesPerSession": (0, 200),
    "hubCallsPerSession": (0, 300),
}


def _merge_architect(current: ArchitectSettings, patch: dict[str, Any]) -> ArchitectSettings:
    data = current.model_dump(by_alias=True)
    for key, value in patch.items():
        if key not in data:
            continue
        if key in _ARCHITECT_LIMITS:
            low, high = _ARCHITECT_LIMITS[key]
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise AppError("settings.architect.limit", status_code=400)
        data[key] = value
    return ArchitectSettings.model_validate(data)


def _initial_ollama_runtime(base_url: object) -> str:
    """Settings from before the own runtime: a custom Ollama address stays in use."""
    if not isinstance(base_url, str) or not base_url.strip():
        return "own"
    try:
        normalized = normalize_ollama_base_url(base_url)
    except ValueError:
        return "own"
    return "own" if normalized in _DEFAULT_OLLAMA_URLS else "external"


_DEFAULT_OLLAMA_URLS = {"http://127.0.0.1:11434", "http://localhost:11434"}


def load_settings() -> AppSettings:
    raw = db_get_settings()
    if not raw:
        settings = default_settings()
        _persist(settings)
        return settings
    defaults = default_settings().model_dump(by_alias=True)
    help_raw = raw.get("helpChat") if isinstance(raw.get("helpChat"), dict) else {}
    merged_help = {**defaults["helpChat"], **help_raw}
    architect_raw = raw.get("architect") if isinstance(raw.get("architect"), dict) else {}
    merged_architect = {**defaults["architect"], **architect_raw}
    merged = {**defaults, **raw, "helpChat": merged_help, "architect": merged_architect}
    if "ollamaRuntime" not in raw:
        merged["ollamaRuntime"] = _initial_ollama_runtime(raw.get("ollamaBaseUrl"))
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
    if body.ollama_runtime is not None:
        # Takes effect at the next start; the runtime section offers the restart.
        updates["ollama_runtime"] = body.ollama_runtime
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
    if body.architect is not None:
        updates["architect"] = _merge_architect(current.architect, body.architect)
    if body.network_versions_keep is not None:
        if not 5 <= body.network_versions_keep <= 500:
            raise AppError("settings.versions.invalid", status_code=400)
        updates["network_versions_keep"] = body.network_versions_keep
    settings = current.model_copy(update=updates)
    _persist(settings)
    return settings


def _credential_item(row: dict[str, Any], used: list[str] | None = None) -> CredentialListItem:
    if used is None:
        used = usage_labels(row["id"])
    return CredentialListItem(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        mask=row["mask"],
        in_use=bool(used),
        used_by=used,
    )


def list_credential_items() -> list[CredentialListItem]:
    rows = list_credentials()
    index = usage_index([row["id"] for row in rows])
    return [_credential_item(row, index[row["id"]]) for row in rows]


def _prepare_secret(kind: str, secret: str) -> tuple[str, str]:
    if kind != "custom":
        return secret, mask_from_secret(secret)
    from app.common.custom_credential import encode_custom_secret, mask_custom, parse_custom_secret

    try:
        parsed = parse_custom_secret(secret)
    except ValueError as exc:
        raise AppError("settings.credentials.customInvalid", status_code=400) from exc
    canonical = encode_custom_secret(parsed)
    return canonical, mask_custom(parsed)


def create_credential(body: CredentialCreate) -> CredentialListItem:
    secret = body.secret.strip()
    if not secret:
        raise AppError("credentials.secret.required", status_code=400)
    secret, mask = _prepare_secret(body.kind, secret)
    cred_id = str(uuid.uuid4())
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
        kind = body.kind or str(existing["kind"])
        secret, mask = _prepare_secret(kind, secret)
        vault_put(cred_id, secret)
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
    wait_ask = None
    if slice_.wait_ask:
        wait_ask = SessionWaitAsk.model_validate(slice_.wait_ask)
    return SessionOut(
        active_network_id=settings.active_network_id,
        active_network_name=name,
        service_status=slice_.service_status,
        run_id=slice_.run_id,
        started_at=slice_.started_at,
        phase=slice_.phase,
        phase_label=slice_.phase_label,
        wait_ask=wait_ask,
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
    for key in ("activeNetworkName", "runId", "startedAt", "phase", "phaseLabel", "waitAsk"):
        if data.get(key) is None:
            data.pop(key, None)
    return data
