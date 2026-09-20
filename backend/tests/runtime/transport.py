from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from app.common.http import client as real_client


def install_transport(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    def wrapped(*, timeout_sec: float = 15.0, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(timeout_sec=timeout_sec, **kwargs)

    monkeypatch.setattr("app.runtime.ollama.client", wrapped)
    monkeypatch.setattr("app.runtime.completions.client", wrapped)
    monkeypatch.setattr("app.runtime.embeddings.client", wrapped)
    monkeypatch.setattr("app.runtime.catalog.client", wrapped)
