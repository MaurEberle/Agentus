"""POST /api/app/open-logs opens the folder with agentus.log (B1). The path is not sent."""

from __future__ import annotations


def test_open_logs_endpoint(client, monkeypatch) -> None:
    opened: list[bool] = []
    monkeypatch.setattr("app.applog.open_log_dir", lambda: opened.append(True) or True)
    response = client.post("/api/app/open-logs")
    assert response.status_code == 200
    assert response.json() == {"opened": True}
    assert opened == [True]
