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
    # Long read waits (LLM generate) must not also block connect for minutes.
    if timeout_sec > 15.0:
        timeout: float | httpx.Timeout = httpx.Timeout(
            connect=10.0,
            read=timeout_sec,
            write=min(60.0, timeout_sec),
            pool=10.0,
        )
    else:
        timeout = timeout_sec
    return httpx.Client(
        timeout=timeout,
        follow_redirects=False,
        headers=headers,
        **kwargs,
    )
