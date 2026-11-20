"""Short tool result facts and clipping for run log lines (B5, B6)."""

from __future__ import annotations

from app.run.log_payloads import clip, clip_strings, tool_result_summary


def test_clip_marks_what_was_cut() -> None:
    assert clip("abc", 5) == "abc"
    assert clip("abcdefgh", 3) == "abc… [+5]"


def test_clip_strings_reaches_nested_values() -> None:
    value = {"path": "a.md", "edits": [{"old": "o" * 10, "new": "n"}], "n": 3}
    assert clip_strings(value, 4) == {"path": "a.md", "edits": [{"old": "oooo… [+6]", "new": "n"}], "n": 3}


def test_read_result_keeps_path_size_and_lines() -> None:
    result = {"ok": True, "result": {"path": "src/a.ts", "content": "x\ny\n", "bytes": 4, "truncated": False}}
    assert tool_result_summary(result) == {"path": "src/a.ts", "bytes": 4, "truncated": False, "lines": 2}


def test_listing_keeps_only_the_count() -> None:
    result = {"ok": True, "result": {"path": ".", "entries": [{"name": "a"}, {"name": "b"}]}}
    assert tool_result_summary(result) == {"path": ".", "entries": 2}


def test_terminal_failure_keeps_exit_code_and_first_error_line() -> None:
    result = {
        "ok": True,
        "result": {
            "exitCode": 1,
            "stdout": "building\n",
            "stderr": "\nsrc/App.tsx(3,1): error TS2304: Cannot find name 'x'.\nmore\n",
            "timedOut": False,
        },
    }
    summary = tool_result_summary(result)
    assert summary["exitCode"] == 1
    assert summary["output"] == "src/App.tsx(3,1): error TS2304: Cannot find name 'x'."


def test_terminal_success_keeps_the_last_output_line() -> None:
    result = {"ok": True, "result": {"exitCode": 0, "stdout": "a\nbuilt in 4.2s\n", "stderr": ""}}
    assert tool_result_summary(result)["output"] == "built in 4.2s"


def test_mcp_text_and_lists() -> None:
    assert tool_result_summary("hello") == {"chars": 5}
    assert tool_result_summary([1, 2, 3]) == {"items": 3}
    assert tool_result_summary(None) is None
    assert tool_result_summary({"ok": False, "result": None, "errorKey": "x"}) is None
