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
