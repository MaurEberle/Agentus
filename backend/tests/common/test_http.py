import httpx

from app.common.http import USER_AGENT, client


def test_client_defaults() -> None:
    with client() as c:
        assert c.follow_redirects is False
        assert c.headers["User-Agent"] == USER_AGENT
        assert USER_AGENT == "Agentus-Network/1.0"
        assert c.timeout.connect == 15.0
        assert c.timeout.read == 15.0


def test_client_custom_timeout() -> None:
    with client(timeout_sec=3.0) as c:
        assert c.timeout.read == 3.0


def test_client_long_timeout_keeps_short_connect() -> None:
    with client(timeout_sec=600.0) as c:
        assert c.timeout.read == 600.0
        assert c.timeout.connect == 10.0


def test_client_sends_user_agent() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["user-agent"])
        return httpx.Response(200, json={"ok": True})

    with client(transport=httpx.MockTransport(handler)) as c:
        response = c.get("http://127.0.0.1/api/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    assert seen == [USER_AGENT]


def test_client_ignores_follow_redirects_kwarg() -> None:
    with client(follow_redirects=True) as c:
        assert c.follow_redirects is False
