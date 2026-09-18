"""Single httpx factory. Runtime, tools, help, and Ollama tags all use this."""

from __future__ import annotations

from typing import Any

import httpx

USER_AGENT = "Agentus-Network/1.0"


def client(*, timeout_sec: float = 15.0, **kwargs: Any) -> httpx.Client:
    """Return a configured ``httpx.Client`` (context-manager capable).

    ``follow_redirects`` is always false — the http tool follows redirects itself.
    Extra kwargs go to ``httpx.Client`` (e.g. ``transport=`` in tests).
    """
    kwargs.pop("follow_redirects", None)
    kwargs.pop("timeout", None)
    headers = httpx.Headers(kwargs.pop("headers", None))
    headers["User-Agent"] = USER_AGENT
    return httpx.Client(
        timeout=timeout_sec,
        follow_redirects=False,
        headers=headers,
        **kwargs,
    )
