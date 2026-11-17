from __future__ import annotations

from app.tools.execute import execute_first_party


def test_unknown_kind() -> None:
    result = execute_first_party("nope")
    assert result.ok is False
    assert result.error_key == "tools.unknownKind"
    dumped = result.model_dump(by_alias=True)
    assert dumped["errorKey"] == "tools.unknownKind"


def test_tool_crash_is_an_internal_error_and_logged(monkeypatch, caplog) -> None:
    """N6: a bug inside a tool looked like an unknown tool kind and left no trace."""
    import logging

    def _boom(config, args):
        raise ZeroDivisionError("bug")

    monkeypatch.setattr("app.tools.execute.run_calculator", _boom)
    with caplog.at_level(logging.ERROR, logger="app.tools.execute"):
        result = execute_first_party("calculator", args={"expression": "1/0"})
    assert result.ok is False
    assert result.error_key == "tools.internalError"
    assert "ZeroDivisionError" in str(result.result)
    assert any("calculator" in record.getMessage() and record.exc_info for record in caplog.records)
