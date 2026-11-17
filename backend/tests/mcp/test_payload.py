from __future__ import annotations

from app.mcp.payload import coerce_tool_arguments, compact_tool_result, format_tool_result


def test_compact_github_search_keeps_names() -> None:
    raw = {
        "total_count": 2,
        "incomplete_results": False,
        "items": [
            {
                "id": 1,
                "full_name": "me/repo",
                "html_url": "https://github.com/me/repo",
                "owner": {"login": "me", "id": 9},
                "stargazers_count": 3,
            },
            {"full_name": "me/other", "html_url": "https://github.com/me/other"},
        ],
    }
    out = compact_tool_result(raw)
    assert isinstance(out, dict)
    assert out["total_count"] == 2
    assert out["items"][0] == {
        "full_name": "me/repo",
        "html_url": "https://github.com/me/repo",
        "stargazers_count": 3,
    }
    assert "owner" not in out["items"][0]


def test_format_tool_result_truncates() -> None:
    text = format_tool_result({"blob": "x" * 8000}, limit=50)
    assert text.endswith("… truncated")
    assert len(text) < 80


def test_coerce_whole_floats() -> None:
    assert coerce_tool_arguments({"page": 2.0, "query": "user:me", "ok": True}) == {
        "page": 2,
        "query": "user:me",
        "ok": True,
    }


def test_long_result_stays_valid_json_and_keeps_later_fields() -> None:
    import json

    raw = {"ok": True, "result": {"exitCode": 1, "stdout": "o" * 30_000, "stderr": "boom", "timedOut": False}}
    text = format_tool_result(raw)
    assert len(text) <= 4000
    data = json.loads(text)
    assert data["truncated"] is True
    assert data["result"]["stderr"] == "boom"
    assert data["result"]["timedOut"] is False
    assert "characters omitted" in data["result"]["stdout"]
    # Head and tail of the long field survive.
    assert data["result"]["stdout"].startswith("ooo") and data["result"]["stdout"].endswith("ooo")
    # The caller's object is not changed.
    assert len(raw["result"]["stdout"]) == 30_000


def test_long_plain_text_keeps_head_and_tail() -> None:
    text = format_tool_result("A" * 5000 + "TAIL")
    assert len(text) <= 4000
    assert text.startswith("AAA") and text.endswith("TAIL")
    assert "characters omitted" in text


def test_many_small_values_fall_back_to_a_preview() -> None:
    import json

    raw = [{"id": index, "name": f"n{index}"} for index in range(2000)]
    text = format_tool_result(raw)
    assert len(text) <= 4000
    data = json.loads(text)
    assert data["truncated"] is True and data["totalChars"] > 4000
