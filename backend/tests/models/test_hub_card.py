"""Model cards from the Hub: fetched once, shown as safe Markdown (no raw HTML)."""

from __future__ import annotations

import httpx

from app.llm import hub
from app.llm.card_markdown import card_markdown, resolve_url

REPO = "org/model-GGUF"

CARD = """---
license: other
base_model:
- org/model
---

<div align="center">
  <a href="https://example.com/chat"><img src="https://img.shields.io/badge/Chat-Model-green" alt="Chat"></a>
  <img src="./figures/plot.png" width="600">
</div>

<h2 align="center">Overview</h2>

Run it: https://llama.app &amp; enjoy. The writer_agent uses `<think>` tags and <b>bold</b> text.

<!-- hidden note -->
<script>alert(1)</script>

<table>
  <tr><th>Benchmark</th><th>Score</th></tr>
  <tr><td><a href="/datasets/x">X</a></td><td>91 | 92</td></tr>
</table>

<details><summary><b>More</b></summary>

See [the license](LICENSE) and [section](#usage) or ![logo](assets/logo.svg).

</details>

```html
<div>kept as code</div>
```

> [!IMPORTANT]
> Converted automatically.
"""


def test_front_matter_goes_and_html_becomes_markdown() -> None:
    text = card_markdown(CARD, REPO)
    assert not text.startswith("---") and "license:" not in text
    # Badge links keep their image only; relative images point into the repo.
    assert "![Chat](https://img.shields.io/badge/Chat-Model-green)" in text
    assert "[![Chat]" not in text and "](https://example.com/chat)" not in text
    assert f"![](https://huggingface.co/{REPO}/resolve/main/figures/plot.png)" in text
    assert "## Overview" in text and "**bold**" in text and "&amp;" not in text and "& enjoy" in text
    # Inline code and code blocks stay as written, comments and scripts are gone.
    assert "`<think>`" in text and "<div>kept as code</div>" in text
    assert "hidden note" not in text and "alert(1)" not in text
    # Tables become Markdown tables; a pipe inside a cell is escaped.
    assert "| Benchmark | Score |" in text and "| --- | --- |" in text
    assert "| [X](https://huggingface.co/datasets/x) | 91 \\| 92 |" in text
    assert "**More**" in text and "****" not in text
    assert f"[the license](https://huggingface.co/{REPO}/blob/main/LICENSE)" in text
    assert "[section]" not in text and "section" in text
    assert f"![logo](https://huggingface.co/{REPO}/resolve/main/assets/logo.svg)" in text
    assert "> [!IMPORTANT]" in text
    # No tag the viewer would show as text survives outside code.
    prose = text.split("```html")[0] + text.split("```", 2)[-1]
    assert "<div" not in prose and "<img" not in prose and "<table" not in prose


def test_urls_resolve_into_the_repo_or_are_dropped() -> None:
    assert resolve_url("https://a.b/c", REPO, image=True) == "https://a.b/c"
    assert resolve_url("./x.png", REPO, image=True) == f"https://huggingface.co/{REPO}/resolve/main/x.png"
    assert resolve_url("docs/a.md", REPO, image=False) == f"https://huggingface.co/{REPO}/blob/main/docs/a.md"
    assert resolve_url("/org/other", REPO, image=False) == "https://huggingface.co/org/other"
    assert resolve_url("//cdn.x/y.png", REPO, image=True) == "https://cdn.x/y.png"
    assert resolve_url("https://x/a b(c).png", REPO, image=True) == "https://x/a%20b%28c%29.png"
    for bad in ("#top", "javascript:alert(1)", "data:image/png;base64,AA", "file:///c"):
        assert resolve_url(bad, REPO, image=False) is None
    assert resolve_url("mailto:a@b.c", REPO, image=True) is None


def _fake_hub(monkeypatch, handler) -> list[str]:
    sent: list[str] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url))
        return handler(request)

    monkeypatch.setitem(hub._COOLDOWN, "until", 0.0)
    monkeypatch.setattr(hub, "_CARD_CACHE", {})
    monkeypatch.setattr(hub, "client", lambda **_: httpx.Client(transport=httpx.MockTransport(record)))
    return sent


def test_the_card_is_fetched_once_and_served_cleaned(client, monkeypatch) -> None:
    sent = _fake_hub(monkeypatch, lambda request: httpx.Response(200, text=CARD))
    first = client.get("/api/models/hub/card", params={"id": REPO}).json()
    assert first["id"] == REPO and first["url"] == f"https://huggingface.co/{REPO}"
    assert "## Overview" in first["markdown"] and "messageKey" not in first and first["truncated"] is False
    assert sent == [f"https://huggingface.co/{REPO}/raw/main/README.md"]
    again = client.get("/api/models/hub/card", params={"id": REPO.upper()}).json()
    assert again["markdown"] == first["markdown"] and len(sent) == 1


def test_missing_locked_and_rate_limited_cards(client, monkeypatch) -> None:
    status = {"code": 404}
    sent = _fake_hub(monkeypatch, lambda request: httpx.Response(status["code"], text="nope"))
    assert client.get("/api/models/hub/card", params={"id": "a/none"}).json()["messageKey"] == "models.hub.card.none"
    status["code"] = 403
    assert client.get("/api/models/hub/card", params={"id": "a/locked"}).json()["messageKey"] == "models.hub.card.locked"
    assert client.get("/api/models/hub/card", params={"id": "not a repo"}).json()["messageKey"] == "models.hub.invalid"
    status["code"] = 429
    limited = client.get("/api/models/hub/card", params={"id": "a/busy"}).json()
    assert limited["messageKey"] == "models.hub.rateLimited" and limited["retryAfter"] >= 1
    # A rate limit is not remembered as "no card": the next try after the wait asks again.
    assert "a/busy" not in hub._CARD_CACHE
    assert len(sent) == 3


def test_a_huge_card_is_cut(monkeypatch) -> None:
    body = "# Big\n\n" + ("word " * 100_000)
    _fake_hub(monkeypatch, lambda request: httpx.Response(200, text=body))
    card = hub.repo_card(REPO)
    assert card.truncated is True and card.markdown.startswith("# Big")
    assert len(card.markdown) <= hub.CARD_MAX_BYTES


def test_the_base_model_comes_from_the_card_header() -> None:
    from app.llm.card_markdown import card_base_model

    assert card_base_model(CARD) == "org/model"
    assert card_base_model("---\nbase_model: Qwen/Qwen3-14B\n---\n# x") == "Qwen/Qwen3-14B"
    assert card_base_model("---\nbase_model: ['a/b', 'c/d']\nlicense: mit\n---\n") == "a/b"
    assert card_base_model("---\nbase_model:\n  - \"x/y\"  # quantized\n---\n") == "x/y"
    assert card_base_model("---\nlicense: mit\n---\n# no base") is None
    assert card_base_model("# no header\nbase_model: a/b") is None
    assert card_base_model("---\nbase_model: not a repo\n---\n") is None


def test_the_card_response_names_the_base_model(monkeypatch) -> None:
    _fake_hub(monkeypatch, lambda request: httpx.Response(200, text=CARD))
    assert hub.repo_card(REPO).base_model == "org/model"
    own = "---\nbase_model: org/self\n---\n# Self"
    _fake_hub(monkeypatch, lambda request: httpx.Response(200, text=own))
    assert hub.repo_card("org/self").base_model is None


def test_installed_models_know_the_repo_of_their_card() -> None:
    from app.llm.catalog import card_repo

    assert card_repo("hf.co/unsloth/Qwen3-GGUF:Q4_K_M", None) == "unsloth/Qwen3-GGUF"
    assert card_repo("llama3.2:1b", {"model_info": {"general.basename": "Llama-3.2"}}) is None
    assert card_repo("qwen3:14b", {"model_info": {"general.source.huggingface.repository": "Qwen/Qwen3-14B"}}) == "Qwen/Qwen3-14B"
    assert card_repo("x:1b", {"model_info": {"general.base_model.0.repo_url": "https://huggingface.co/org/base"}}) == "org/base"
    assert card_repo("x:1b", {"model_info": {"general.source.url": "https://github.com/org/repo"}}) is None
    assert card_repo("x:1b", None) is None
