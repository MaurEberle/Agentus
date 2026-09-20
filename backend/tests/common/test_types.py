from typing import get_args

from app.common.types import (
    CREDENTIAL_KINDS,
    PROVIDERS,
    STORE_IDS,
    CredentialKind,
    Provider,
    StoreId,
)


def test_providers_have_no_lmstudio() -> None:
    assert "lmstudio" not in PROVIDERS
    assert set(PROVIDERS) == {"ollama", "xai", "openai", "anthropic", "gemini", "openai_compat"}
    assert PROVIDERS == get_args(Provider)


def test_store_ids() -> None:
    assert STORE_IDS == get_args(StoreId)
    assert set(STORE_IDS) == {"settings", "help", "workspace", "history"}


def test_credential_kinds_include_postgres_for_mcp() -> None:
    assert "postgres" in CREDENTIAL_KINDS
    assert {"openai", "anthropic", "gemini", "xai"} <= set(CREDENTIAL_KINDS)
    assert CREDENTIAL_KINDS == get_args(CredentialKind)
    assert "lmstudio" not in CREDENTIAL_KINDS
