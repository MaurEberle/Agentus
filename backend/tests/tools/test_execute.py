from __future__ import annotations

from app.tools.execute import execute_first_party


def test_unknown_kind() -> None:
    result = execute_first_party("nope")
    assert result.ok is False
    assert result.error_key == "tools.unknownKind"
    dumped = result.model_dump(by_alias=True)
    assert dumped["errorKey"] == "tools.unknownKind"
