from __future__ import annotations

from app.host.single_instance import MUTEX_NAME, WINDOW_TITLE, acquire
from app.host.window import on_closing, run_host
from app.main import _want_host


def test_mutex_name() -> None:
    assert MUTEX_NAME == "Local\\AgentusNetworkDesktopMutex"
    assert WINDOW_TITLE == "Agentus Network"


def test_want_host_dev(monkeypatch) -> None:
    monkeypatch.setenv("AGENTUS_NETWORK_DEV", "1")
    monkeypatch.delenv("AGENTUS_NETWORK_NO_HOST", raising=False)
    assert _want_host() is False
    monkeypatch.delenv("AGENTUS_NETWORK_DEV")
    monkeypatch.setenv("AGENTUS_NETWORK_NO_HOST", "1")
    assert _want_host() is False


def test_run_host_second_instance_skips_uvicorn(monkeypatch) -> None:
    called = {"uvicorn": 0}

    monkeypatch.setattr("app.host.window.acquire", lambda: False)

    def _start(*_a, **_k):
        called["uvicorn"] += 1
        raise AssertionError("must not start uvicorn")

    monkeypatch.setattr("app.host.window.start_uvicorn", _start)
    run_host("127.0.0.1", 8765)
    assert called["uvicorn"] == 0


def test_on_closing_posts_stop(monkeypatch) -> None:
    seen: list[str] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kwargs):
            seen.append(url)
            return type("R", (), {"status_code": 200})()

    monkeypatch.setattr("app.common.http.client", lambda **k: FakeClient())
    assert on_closing(object(), 8765) is True
    assert seen == ["http://127.0.0.1:8765/api/run/stop"]
