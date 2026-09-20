"""Single source for provider and store literals. Import; do not redefine."""

from typing import Literal, get_args

Provider = Literal["ollama", "xai", "openai", "anthropic", "gemini", "openai_compat"]
PROVIDERS: tuple[Provider, ...] = get_args(Provider)
CLOUD_CATALOG_PROVIDERS: tuple[Provider, ...] = ("xai", "openai", "anthropic", "gemini")
NEEDS_CREDENTIAL: frozenset[Provider] = frozenset((*CLOUD_CATALOG_PROVIDERS, "openai_compat"))

HelpProvider = Literal["ollama", "xai", "openai", "anthropic", "gemini", "openai_compat", ""]
EmbeddingProvider = Literal["ollama", "openai", "gemini", "openai_compat", ""]

CredentialKind = Literal[
    "xai",
    "openai",
    "anthropic",
    "gemini",
    "openai_compat",
    "web_search",
    "github",
    "azure",
    "gitlab",
    "slack",
    "notion",
    "atlassian",
    "linear",
    "postgres",
    "token",
]
CREDENTIAL_KINDS: tuple[CredentialKind, ...] = get_args(CredentialKind)

ServiceStatus = Literal[
    "disconnected",
    "stopped",
    "starting",
    "running",
    "stopping",
    "error",
]

StoreId = Literal["settings", "help", "workspace", "history"]
STORE_IDS: tuple[StoreId, ...] = get_args(StoreId)

DataDirSource = Literal["config", "env", "portable", "default"]
RetentionDays = Literal[30, 90, 365]
