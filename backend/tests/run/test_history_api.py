from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.engine import utc_now
from app.db.runs import insert_run


def test_list_limit(client: TestClient) -> None:
    for i in range(8):
        insert_run(
            id=f"r-{i}",
            network_id="n",
            network_name="n",
            started_at=utc_now(),
            outcome="succeeded",
        )
    response = client.get("/api/runs?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) <= 5
    assert body["items"][0]["runId"] == body["items"][0]["id"]
    assert isinstance(body["items"][0]["models"], list)


def test_list_accepts_stats_limit(client: TestClient) -> None:
    response = client.get("/api/runs?limit=500")
    assert response.status_code == 200
    assert "items" in response.json()


def test_delete_running_forbidden(client: TestClient) -> None:
    insert_run(
        id="run-live",
        network_id="n",
        network_name="n",
        started_at=utc_now(),
        outcome="running",
    )
    response = client.request("DELETE", "/api/runs", json={"ids": ["run-live"]})
    assert response.status_code == 409


def test_calls_follow_the_time_range_and_count_every_call(client: TestClient) -> None:
    """H10: the table per model showed the oldest 500 calls, whatever the range."""
    from app.db.runs import insert_call

    insert_run(id="old", network_id="n", network_name="n", started_at="2026-01-01T10:00:00+00:00", outcome="succeeded")
    insert_run(id="new", network_id="n", network_name="n", started_at="2026-11-10T10:00:00+00:00", outcome="succeeded")
    for index in range(6):
        insert_call(run_id="old", provider="ollama", model="old-model", ok=True, duration_ms=100 + index)
    insert_call(run_id="new", provider="openai", model="gpt-x", ok=True, duration_ms=10, tokens_in=5, tokens_out=7)
    insert_call(run_id="new", provider="openai", model="gpt-x", ok=True, duration_ms=30, tokens_in=1, tokens_out=1)
    insert_call(run_id="new", provider="openai", model="gpt-x", ok=False, duration_ms=50, error_message="runtime.timeout")
    insert_call(run_id="new", provider="ollama", model="local", ok=True)

    recent = client.get(
        "/api/runs/calls",
        params={"from": "2026-11-01T00:00:00+00:00", "to": "2026-11-30T00:00:00+00:00", "limit": 2},
    ).json()
    # The page is small and newest first; the statistics cover the whole range.
    assert len(recent["items"]) == 2
    assert recent["items"][0]["model"] == "local"
    assert all(item["runId"] == "new" for item in recent["items"])
    assert recent["byModel"] == [
        {
            "provider": "openai",
            "model": "gpt-x",
            "calls": 3,
            "ok": 2,
            "error": 1,
            "medianMs": 30.0,
            "tokensIn": 6,
            "tokensOut": 8,
        },
        {
            "provider": "ollama",
            "model": "local",
            "calls": 1,
            "ok": 1,
            "error": 0,
            "medianMs": None,
            "tokensIn": None,
            "tokensOut": None,
        },
    ]

    everything = client.get("/api/runs/calls", params={"limit": 500}).json()
    assert {row["model"]: row["calls"] for row in everything["byModel"]} == {
        "old-model": 6,
        "gpt-x": 3,
        "local": 1,
    }
    old = next(row for row in everything["byModel"] if row["model"] == "old-model")
    assert old["medianMs"] == 102.5
