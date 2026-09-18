from __future__ import annotations

from urllib.parse import urlparse


def is_allowed_url(url: str, port: int) -> bool:
    if url in {"about:blank", "about:blank/"}:
        return True
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return False
    if parsed.port is None or parsed.port == -1:
        return True
    return parsed.port == port
