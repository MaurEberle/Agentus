from __future__ import annotations

from app.help.models import HelpChatStatus

_degraded: bool = False


def set_degraded(value: bool) -> None:
    global _degraded
    _degraded = bool(value)


def get_degraded() -> bool:
    return _degraded


def get_settings_merged():
    try:
        from app.settings.service import load_settings

        return load_settings()
    except Exception:
        from app.db.settings import get_settings as db_get
        from app.settings.defaults import default_settings
        from app.settings.models import AppSettings

        raw = db_get()
        if not raw:
            return default_settings()
        return AppSettings.model_validate({**default_settings().model_dump(by_alias=True), **raw})


def get_status() -> HelpChatStatus:
    settings = get_settings_merged()
    help_chat = settings.help_chat
    configured = bool(help_chat.provider and help_chat.model.strip())
    return HelpChatStatus(
        configured=configured,
        onboarding_seen=settings.chat_onboarding_seen,
        web_search_enabled=help_chat.web_search_enabled,
        degraded=get_degraded(),
    )


def ping_help_llm():
    from app.runtime.completions import complete, test_llm
    from app.runtime.errors import RuntimeApiError
    from app.runtime.models import ChatMessage, CompletionRequest, PingResult, TestLlmRequest

    status = get_status()
    if not status.configured:
        return PingResult(ok=False, message_key="help.unconfigured")
    settings = get_settings_merged()
    help_chat = settings.help_chat
    model = effective_help_model()
    if get_degraded() and help_chat.provider == "ollama":
        try:
            complete(
                CompletionRequest(
                    provider="ollama",
                    model=model,
                    messages=[ChatMessage(role="user", content="ping")],
                    credential_id=help_chat.credential_id,
                    max_tokens=1,
                    ollama_options={"num_gpu": 0},
                    timeout_sec=15,
                )
            )
        except RuntimeApiError as exc:
            return PingResult(ok=False, message_key=exc.error_key)
        return PingResult(ok=True)
    return test_llm(
        TestLlmRequest(
            provider=help_chat.provider,  # type: ignore[arg-type]
            model=model,
            credential_id=help_chat.credential_id,
        )
    )


def effective_help_model() -> str:
    settings = get_settings_merged()
    help_chat = settings.help_chat
    if get_degraded() and help_chat.provider == "ollama":
        return (help_chat.fallback_model or "llama3.2:1b").strip() or "llama3.2:1b"
    return help_chat.model.strip()
