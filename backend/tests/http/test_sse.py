from __future__ import annotations

from app.http.sse import sse_comment, sse_event, sse_ping


def test_sse_event_log_run_id() -> None:
    raw = sse_event("log", {"runId": "a"})
    text = raw.decode("utf-8")
    assert text.startswith("event: log\n")
    assert '"runId"' in text
    assert '"a"' in text
    assert text.endswith("\n\n")


def test_sse_event_null_data() -> None:
    text = sse_event("done", None).decode("utf-8")
    assert "data: null\n" in text


def test_sse_ping_comment() -> None:
    assert sse_ping() == b": ping\n\n"
    assert sse_comment("keep") == b": keep\n\n"
