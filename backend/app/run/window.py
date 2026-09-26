"""Context window for one model call. The ladder steps up and does not step down."""

from __future__ import annotations

from dataclasses import dataclass

from app.runtime.completions import estimate_token_count
from app.runtime.models import ChatMessage

# Fixed room for the answer when the node has no maxTokens.
CONTEXT_RESERVE_TOKENS = 1024
_LADDER = (8192, 16384, 32768, 65536)
_SMALL = 8192


@dataclass(frozen=True)
class WindowChoice:
    """``num_ctx`` is sent only when set. ``fits`` false means do not call."""

    num_ctx: int | None
    context_max: int | None
    fits: bool


def prompt_tokens(messages: list[ChatMessage]) -> int:
    parts: list[str] = []
    for message in messages:
        if message.content:
            parts.append(message.content)
        for call in message.tool_calls or []:
            parts.append(call.name or "")
            parts.append(call.arguments or "")
    return estimate_token_count("\n".join(parts))


def prompt_need(messages: list[ChatMessage], max_tokens: int | None) -> int:
    reserve = max_tokens if isinstance(max_tokens, int) and max_tokens > 0 else CONTEXT_RESERVE_TOKENS
    return prompt_tokens(messages) + reserve


def choose_window(
    *,
    need: int,
    preferred: int | None,
    loaded: int | None,
    raised: int | None,
    architecture_max: int | None,
    provider: str,
) -> WindowChoice:
    """Pick the smallest step that holds ``need`` and respects the node's wish.

    Ollama keeps a raised window for the rest of the run. A prompt above 8192
    never stays on an 8192 window. Cloud providers are not sent ``num_ctx``.
    """
    if provider != "ollama":
        cap = preferred if isinstance(preferred, int) and preferred > 0 else None
        if cap is None:
            return WindowChoice(num_ctx=None, context_max=None, fits=True)
        return WindowChoice(num_ctx=None, context_max=cap, fits=need <= cap)

    cap = architecture_max if isinstance(architecture_max, int) and architecture_max > 0 else _LADDER[-1]
    steps = [step for step in _LADDER if step <= cap]
    if cap not in steps:
        steps.append(cap)
        steps.sort()
    floor = 0
    if isinstance(preferred, int) and preferred > 0:
        floor = preferred
    if isinstance(raised, int) and raised > floor:
        floor = raised
    sticky = max(raised or 0, loaded or 0)
    fitting = [step for step in steps if step >= need and step >= floor]
    if fitting:
        chosen = min(fitting)
    elif cap >= need and cap >= floor:
        chosen = cap
    else:
        return WindowChoice(num_ctx=None, context_max=loaded or raised, fits=False)
    if sticky >= need and sticky >= floor and sticky > chosen:
        chosen = sticky
    if need > _SMALL and chosen <= _SMALL:
        return WindowChoice(num_ctx=None, context_max=chosen, fits=False)
    if (
        preferred is None
        and raised is None
        and loaded is None
        and need <= _SMALL
        and chosen <= _SMALL
    ):
        return WindowChoice(num_ctx=None, context_max=None, fits=True)
    if (
        preferred is None
        and raised is None
        and loaded is not None
        and loaded <= _SMALL
        and need <= _SMALL
        and chosen <= _SMALL
    ):
        return WindowChoice(num_ctx=None, context_max=loaded, fits=True)
    return WindowChoice(num_ctx=chosen, context_max=chosen, fits=True)


def loaded_context(tag: str, *, base_url: str | None = None) -> int | None:
    """Read ``context_length`` from ``/api/ps``. Missing on older daemons."""
    from app.runtime.ollama import _root
    from app.common.http import client
    from app.runtime.errors import raise_for_status, response_json

    url = f"{_root(base_url)}/api/ps"
    try:
        with client(timeout_sec=2.0) as http:
            response = http.get(url)
        raise_for_status(response)
        payload = response_json(response)
    except Exception:
        return None
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return None
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if name != tag:
            continue
        found = _context_field(item)
        if found is not None:
            return found
        details = item.get("details")
        if isinstance(details, dict):
            found = _context_field(details)
            if found is not None:
                return found
    return None


def architecture_context(tag: str, *, base_url: str | None = None) -> int | None:
    """Model context length from ``/api/show``, used as the top of the ladder."""
    from app.runtime.ollama import _root
    from app.common.http import client
    from app.runtime.errors import raise_for_status, response_json

    url = f"{_root(base_url)}/api/show"
    try:
        with client(timeout_sec=2.0) as http:
            response = http.post(url, json={"model": tag})
        raise_for_status(response)
        payload = response_json(response)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    info = payload.get("model_info")
    if not isinstance(info, dict):
        return None
    found: int | None = None
    for key, value in info.items():
        if str(key).endswith("context_length") and isinstance(value, int) and value > 0:
            found = value
    return found


def _context_field(item: dict) -> int | None:
    for key in ("context_length", "contextLength"):
        value = item.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None
