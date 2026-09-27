import httpx

from app.run.window import (
    architecture_context,
    choose_window,
    loaded_context,
    prompt_need,
)
from app.runtime.models import ChatMessage


def _choice(**kwargs):
    base = {
        "preferred": None,
        "loaded": None,
        "raised": None,
        "architecture_max": None,
        "provider": "ollama",
    }
    base.update(kwargs)
    return choose_window(**base)


def test_need_above_8k_steps_up() -> None:
    choice = _choice(need=9000)
    assert choice.fits is True
    assert choice.num_ctx == 16384


def test_preferred_8k_is_sent_for_a_small_prompt() -> None:
    choice = _choice(need=1000, preferred=8192)
    assert choice.num_ctx == 8192
    assert choice.context_max == 8192
    assert choice.fits is True


def test_preferred_above_a_step_uses_the_next_step() -> None:
    choice = _choice(need=1000, preferred=20000)
    assert choice.num_ctx == 32768


def test_loaded_window_does_not_step_down() -> None:
    choice = _choice(need=1000, loaded=32768)
    assert choice.num_ctx == 32768
    assert choice.context_max == 32768


def test_loaded_8k_steps_up_when_the_prompt_does_not_fit() -> None:
    choice = _choice(need=9000, loaded=8192)
    assert choice.num_ctx == 16384
    assert choice.fits is True


def test_need_above_architecture_does_not_fit() -> None:
    choice = _choice(need=70000, architecture_max=65536)
    assert choice.fits is False
    assert choice.num_ctx is None


def test_small_prompt_without_a_wish_omits_num_ctx() -> None:
    choice = _choice(need=1000)
    assert choice.num_ctx is None
    assert choice.context_max is None
    assert choice.fits is True


def test_cloud_never_sends_num_ctx() -> None:
    open_choice = _choice(need=1000, provider="openai")
    assert open_choice.num_ctx is None
    assert open_choice.fits is True
    assert open_choice.context_max is None
    capped = _choice(need=1000, preferred=8192, provider="openai")
    assert capped.num_ctx is None
    assert capped.context_max == 8192
    assert capped.fits is True
    overflow = _choice(need=9000, preferred=8192, provider="openai")
    assert overflow.num_ctx is None
    assert overflow.fits is False


def test_prompt_need_reserves_room_for_the_answer() -> None:
    messages = [ChatMessage(role="user", content="abcd")]
    assert prompt_need(messages, None) == 1 + 1024
    assert prompt_need(messages, 0) == 1 + 1024
    assert prompt_need(messages, 200) == 1 + 200


def test_loaded_context_reads_either_field_name(monkeypatch) -> None:
    payloads = [
        {"models": [{"name": "m", "context_length": 16384}]},
        {"models": [{"name": "m", "contextLength": 32768}]},
        {"models": [{"name": "m", "details": {"context_length": 8192}}]},
    ]
    seen: list[int | None] = []

    def install(payload: dict) -> None:
        class Client:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def get(self, url):
                return httpx.Response(200, json=payload)

        monkeypatch.setattr("app.common.http.client", lambda *args, **kwargs: Client())

    for payload in payloads:
        install(payload)
        seen.append(loaded_context("m"))
    assert seen == [16384, 32768, 8192]
    install({"models": [{"name": "other", "context_length": 8192}]})
    assert loaded_context("m") is None


def test_architecture_context_reads_model_info(monkeypatch) -> None:
    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, json=None):
            return httpx.Response(200, json={"model_info": {"llama.context_length": 32768}})

    monkeypatch.setattr("app.common.http.client", lambda *args, **kwargs: Client())
    assert architecture_context("m") == 32768


def test_context_lookups_swallow_errors(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise OSError("down")

    monkeypatch.setattr("app.common.http.client", boom)
    assert loaded_context("m") is None
    assert architecture_context("m") is None
