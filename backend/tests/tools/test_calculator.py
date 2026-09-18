from __future__ import annotations

from app.tools.execute import execute_first_party


def test_precedence() -> None:
    result = execute_first_party("calculator", args={"expression": "2+3*4"})
    assert result.ok is True
    assert result.result == {"value": 14}


def test_import_rejected() -> None:
    result = execute_first_party("calculator", args={"expression": '__import__("os")'})
    assert result.ok is False
    assert result.error_key == "tools.calculator.invalidExpression"


def test_pow_exponent_too_large() -> None:
    result = execute_first_party("calculator", args={"expression": "2**99"})
    assert result.ok is False
    assert result.error_key == "tools.calculator.invalidExpression"
