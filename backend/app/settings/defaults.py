"""Installer-aligned first-run settings. The one place help-chat models are seeded."""

from __future__ import annotations

from app.settings.models import AppSettings, HelpChatSettings

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"


def default_settings() -> AppSettings:
    return AppSettings(
        ollama_base_url=DEFAULT_OLLAMA_BASE_URL,
        openai_compat_base_url=None,
        help_chat_fab_visible=True,
        help_chat=HelpChatSettings(
            provider="ollama",
            model="llama3.2:1b",
            embedding_provider="ollama",
            embedding_model="nomic-embed-text",
            fallback_model="llama3.2:1b",
        ),
        active_network_id=None,
        history_retention_days=90,
        chat_onboarding_seen=False,
    )
